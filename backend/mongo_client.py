from pymongo import MongoClient
from datetime import datetime, timezone
import os

# ── Connection ──────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["narcotrace"]
alerts_collection = db["alerts"]

# Create indexes so queries are fast
alerts_collection.create_index("risk_level")
alerts_collection.create_index("platform")
alerts_collection.create_index("timestamp")


# ── Save ────────────────────────────────────────────────────────────────

def save_alert_to_db(alert_doc: dict):
    """
    Saves a scored alert to MongoDB.
    Adds a timestamp automatically.
    """
    alert_doc["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Upsert: if same message_id exists, update it; else insert fresh
    alerts_collection.update_one(
        {"message_id": alert_doc["message_id"]},
        {"$set": alert_doc},
        upsert=True
    )


# ── Fetch ───────────────────────────────────────────────────────────────

def get_alerts_from_db(
    risk_level: str = None,
    platform: str = None,
    limit: int = 50
) -> list[dict]:
    """
    Fetches alerts from MongoDB with optional filters.
    Returns newest first.
    """
    query = {}

    if risk_level:
        query["risk_level"] = risk_level
    if platform:
        query["platform"] = platform

    cursor = (
        alerts_collection
        .find(query, {"_id": 0})   # exclude internal MongoDB _id field
        .sort("timestamp", -1)      # newest first
        .limit(limit)
    )

    return list(cursor)
