from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from mongo_client import get_alerts_from_db, save_alert_to_db
from neo4j_client import get_network_graph, add_user_node, add_contact_edge
from image_analyzer import analyze_image

router = APIRouter()

# ──────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    message_id: str
    text: str
    sender_id: str
    platform: str                  # "telegram" or "instagram"
    image_url: Optional[str] = None

class AnalyzeResponse(BaseModel):
    message_id: str
    risk_score: float              # 0 to 100
    risk_level: str                # "low", "medium", "high"
    flags: list[str]               # e.g. ["drug_slang", "suspicious_image"]
    recommendation: str

class AlertItem(BaseModel):
    message_id: str
    sender_id: str
    platform: str
    text: str
    risk_score: float
    risk_level: str
    flags: list[str]
    timestamp: str

class NetworkNode(BaseModel):
    id: str
    label: str
    risk_level: str

class NetworkEdge(BaseModel):
    source: str
    target: str
    relationship: str

class NetworkResponse(BaseModel):
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]


# ──────────────────────────────────────────────
# ROUTE 1: POST /analyze
# Member 1 calls this internally after scraping.
# Frontend can also call it for manual testing.
# ──────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_message(req: AnalyzeRequest):
    """
    Receives a scraped message, runs NLP + image analysis,
    calculates risk score, saves to MongoDB, updates Neo4j graph.
    """
    flags = []
    score = 0.0

    # --- Step 1: Get NLP risk score from Member 1's module ---
    # We import it here so Member 1 can develop it independently
    try:
        from risk_scorer import score_message
        nlp_result = score_message(req.text)
        score += nlp_result["score"]
        flags.extend(nlp_result["flags"])
    except ImportError:
        # Member 1 hasn't built this yet — use placeholder
        score += 30.0
        flags.append("nlp_module_pending")

    # --- Step 2: Image analysis (CLIP) ---
    if req.image_url:
        try:
            img_result = await analyze_image(req.image_url)
            score += img_result["score"]
            if img_result["flagged"]:
                flags.append("suspicious_image")
        except Exception:
            pass  # Image analysis optional — don't crash if it fails

    # --- Step 3: Determine risk level ---
    score = min(score, 100.0)
    if score >= 70:
        risk_level = "high"
        recommendation = "Escalate to law enforcement immediately"
    elif score >= 40:
        risk_level = "medium"
        recommendation = "Flag for human analyst review"
    else:
        risk_level = "low"
        recommendation = "Monitor — no immediate action needed"

    # --- Step 4: Save to MongoDB ---
    alert_doc = {
        "message_id": req.message_id,
        "sender_id": req.sender_id,
        "platform": req.platform,
        "text": req.text,
        "risk_score": score,
        "risk_level": risk_level,
        "flags": flags,
    }
    save_alert_to_db(alert_doc)

    # --- Step 5: Update Neo4j network graph ---
    try:
        add_user_node(req.sender_id, risk_level)
    except Exception:
        pass  # Graph update failure should not block the API response

    return AnalyzeResponse(
        message_id=req.message_id,
        risk_score=round(score, 2),
        risk_level=risk_level,
        flags=flags,
        recommendation=recommendation
    )


# ──────────────────────────────────────────────
# ROUTE 2: GET /alerts
# Frontend Member 3 uses this to populate the
# dashboard alerts table.
# ──────────────────────────────────────────────

@router.get("/alerts", response_model=list[AlertItem])
def get_alerts(
    risk_level: Optional[str] = None,   # filter: "high", "medium", "low"
    platform: Optional[str] = None,     # filter: "telegram", "instagram"
    limit: int = 50
):
    """
    Returns flagged messages from MongoDB.
    Supports optional filtering by risk level and platform.
    """
    try:
        alerts = get_alerts_from_db(
            risk_level=risk_level,
            platform=platform,
            limit=limit
        )
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# ROUTE 3: GET /network
# Frontend Member 4 uses this to draw the D3.js
# force-directed graph of connected accounts.
# ──────────────────────────────────────────────

@router.get("/network", response_model=NetworkResponse)
def get_network(account_id: Optional[str] = None, depth: int = 2):
    """
    Returns nodes (accounts) and edges (connections) from Neo4j.
    If account_id given, returns graph within `depth` hops of that account.
    If no account_id, returns all high-risk accounts and their connections.
    """
    try:
        graph = get_network_graph(account_id=account_id, depth=depth)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# ROUTE 4: POST /network/link
# Called internally when two users contact each other
# ──────────────────────────────────────────────

@router.post("/network/link")
def link_accounts(source_id: str, target_id: str, relationship: str = "CONTACTED"):
    """
    Creates a relationship edge between two accounts in Neo4j.
    """
    try:
        add_contact_edge(source_id, target_id, relationship)
        return {"status": "edge created", "source": source_id, "target": target_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
