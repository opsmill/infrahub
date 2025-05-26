from infrahub.database import InfrahubDatabase


async def verify_no_duplicate_relationships(db: InfrahubDatabase) -> None:
    """
    Verify that no duplicate active relationships exist at the database level
    A duplicate is defined as
    - connecting the same two nodes
    - having the same identifier
    - having the same direction (inbound, outbound, bidirectional)
    - having the same branch
    A more thorough check that no duplicates exist at any point in time is possible, but more complex
    """
    query = """
MATCH (a:Node)-[e1:IS_RELATED {status: "active"}]-(rel:Relationship)-[e2:IS_RELATED {branch: e1.branch, status: "active"}]-(b:Node)
WHERE a.uuid <> b.uuid
AND e1.to IS NULL
AND e2.to IS NULL
WITH a, rel.name AS rel_name, b, e1.branch AS branch, CASE
    WHEN startNode(e1) = a AND startNode(e2) = rel THEN "out"
    WHEN startNode(e1) = rel AND startNode(e2) = b THEN "in"
    ELSE "bidir"
END AS direction, COUNT(*) AS num_duplicates
WHERE num_duplicates > 1
RETURN a.uuid AS node_id1, b.uuid AS node_id2, rel_name, branch, direction, num_duplicates
    """
    results = await db.execute_query(query=query)
    for result in results:
        node_id1 = result.get("node_id1")
        node_id2 = result.get("node_id2")
        rel_name = result.get("rel_name")
        branch = result.get("branch")
        direction = result.get("direction")
        num_duplicates = result.get("num_duplicates")
        raise ValueError(
            f"{num_duplicates} duplicate relationships ({branch=},{direction=}) between nodes '{node_id1}' and '{node_id2}'"
            f" with relationship name '{rel_name}'"
        )
