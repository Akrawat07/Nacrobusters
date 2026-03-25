from neo4j import GraphDatabase
import os

# ── Connection ──────────────────────────────────────────────────────────
NEO4J_URI  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "narcotrace123")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


# ── Helper ──────────────────────────────────────────────────────────────

def _run(query: str, **params):
    with driver.session() as session:
        return session.run(query, **params).data()


# ── Node Operations ─────────────────────────────────────────────────────

def add_user_node(user_id: str, risk_level: str = "low"):
    """
    Creates or updates a User node in Neo4j.
    MERGE means: create it if not exists, update if it does.
    """
    _run(
        """
        MERGE (u:User {id: $user_id})
        SET u.risk_level = $risk_level,
            u.updated_at = timestamp()
        """,
        user_id=user_id,
        risk_level=risk_level
    )


# ── Edge Operations ─────────────────────────────────────────────────────

def add_contact_edge(source_id: str, target_id: str, relationship: str = "CONTACTED"):
    """
    Creates a directional relationship between two user accounts.
    Also creates the nodes if they don't already exist.
    """
    _run(
        """
        MERGE (a:User {id: $source_id})
        MERGE (b:User {id: $target_id})
        MERGE (a)-[r:CONTACTED]->(b)
        SET r.type = $relationship,
            r.count = COALESCE(r.count, 0) + 1,
            r.last_seen = timestamp()
        """,
        source_id=source_id,
        target_id=target_id,
        relationship=relationship
    )


# ── Graph Query ─────────────────────────────────────────────────────────

def get_network_graph(account_id: str = None, depth: int = 2) -> dict:
    """
    Returns all nodes and edges for D3.js visualization.

    If account_id given → return the subgraph within `depth` hops.
    If no account_id   → return all high-risk accounts + their connections.
    """
    if account_id:
        # Subgraph around a specific account
        records = _run(
            """
            MATCH path = (start:User {id: $account_id})-[*1..$depth]-(connected:User)
            WITH nodes(path) AS ns, relationships(path) AS rs
            UNWIND ns AS n
            WITH COLLECT(DISTINCT {id: n.id, label: n.id, risk_level: COALESCE(n.risk_level,'low')}) AS nodes,
                 rs
            UNWIND rs AS r
            RETURN nodes,
                   COLLECT(DISTINCT {
                       source: startNode(r).id,
                       target: endNode(r).id,
                       relationship: type(r)
                   }) AS edges
            """,
            account_id=account_id,
            depth=depth
        )
    else:
        # All high-risk nodes and their connections
        records = _run(
            """
            MATCH (u:User)
            WHERE u.risk_level = 'high'
            OPTIONAL MATCH (u)-[r:CONTACTED]-(other:User)
            WITH COLLECT(DISTINCT {id: u.id, label: u.id, risk_level: u.risk_level}) +
                 COLLECT(DISTINCT {id: other.id, label: other.id,
                                   risk_level: COALESCE(other.risk_level,'low')}) AS nodes,
                 COLLECT(DISTINCT {
                     source: startNode(r).id,
                     target: endNode(r).id,
                     relationship: type(r)
                 }) AS edges
            RETURN [n IN nodes WHERE n.id IS NOT NULL] AS nodes, edges
            """
        )

    if not records:
        return {"nodes": [], "edges": []}

    row = records[0]
    return {
        "nodes": row.get("nodes", []),
        "edges": row.get("edges", [])
    }


# ── Cleanup ─────────────────────────────────────────────────────────────

def close():
    driver.close()
