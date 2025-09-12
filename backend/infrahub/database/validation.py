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


async def verify_no_edges_added_after_node_delete(db: InfrahubDatabase) -> None:
    """
    Verify that no edges are added to a Node after it is deleted on a given branch
    """
    query = """
// ------------
// find deleted nodes
// ------------
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE e.status = "deleted" OR e.to IS NOT NULL
WITH DISTINCT n, e.branch AS delete_branch, e.branch_level AS delete_branch_level, CASE
    WHEN e.status = "deleted" THEN e.from
    ELSE e.to
END AS delete_time
// ------------
// find the edges added to the deleted node after the delete time
// ------------
MATCH (n)-[added_e]-(peer)
WHERE added_e.from > delete_time
AND type(added_e) <> "IS_PART_OF"
// if the node was deleted on a branch (delete_branch_level > 1), and then updated on main/global (added_e.branch_level = 1), we can ignore it
AND added_e.branch_level >= delete_branch_level
AND (added_e.branch = delete_branch OR delete_branch_level = 1)
WITH DISTINCT n, delete_branch, delete_time, added_e, peer AS added_peer
// ------------
// get the branched_from for the branch on which the node was deleted
// ------------
CALL (added_e) {
    MATCH (b:Branch {name: added_e.branch})
    RETURN b.branched_from AS added_e_branched_from
}
// ------------
// account for the following situations, given that the edge update time is after the node delete time
//  - deleted on main/global, updated on branch
//    - illegal if the delete is before branch.branched_from
//  - deleted on branch, updated on branch
//    - illegal
// ------------
WITH n, delete_branch, delete_time, added_e, added_peer
WHERE delete_branch = added_e.branch
OR delete_time < added_e_branched_from
RETURN n.uuid AS n_uuid, delete_branch, delete_time, added_e, added_peer
    """
    results = await db.execute_query(query=query)
    error_messages = []
    for result in results:
        n_uuid = result.get("n_uuid")
        delete_branch = result.get("delete_branch")
        delete_time = result.get("delete_time")
        added_e = result.get("added_e")
        added_e_branch = added_e.get("branch")
        added_e_from = added_e.get("from")
        added_peer = result.get("added_peer")
        message = (
            f"Node {n_uuid} was deleted on {delete_branch} at {delete_time} but has an {added_e.type} edge added on"
            f" branch {added_e_branch} at {added_e_from} to {added_peer.element_id}"
        )
        error_messages.append(message)
    if error_messages:
        raise ValueError(error_messages)
