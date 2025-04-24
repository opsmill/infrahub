# deduplicate edges
query = """
MATCH (node_with_dup_edges:Node)-[edge]-(peer)
WITH node_with_dup_edges, type(edge) AS edge_type, edge.status AS edge_status, edge.branch AS edge_branch, peer, count(*) AS num_dup_edges
WHERE num_dup_edges > 1
WITH DISTINCT node_with_dup_edges, edge_type, edge_branch, peer
CALL {
    WITH node_with_dup_edges, edge_type, edge_branch, peer
    MATCH (node_with_dup_edges)-[active_edge {branch: edge_branch, status: "active"}]-(peer)
    WHERE type(active_edge) = edge_type
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_edge
    ORDER BY active_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, head(collect(active_edge.from)) AS active_from
    OPTIONAL MATCH (node_with_dup_edges)-[deleted_edge {branch: edge_branch, status: "deleted"}]->(peer)
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_edge
    ORDER BY deleted_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, head(collect(deleted_edge.from)) AS deleted_from
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_from
        MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_from, active_e
        ORDER BY elementId(active_e)
        LIMIT 1
        SET active_e.from = active_from
        SET active_e.to = deleted_from
        WITH node_with_dup_edges, edge_type, edge_branch, peer
        MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        WITH active_e
        ORDER BY elementId(active_e)
        SKIP 1
        DELETE active_e
    }
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, deleted_from
        MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        WITH node_with_dup_edges, edge_type, edge_branch, peer, deleted_from, deleted_e
        ORDER BY elementId(deleted_e)
        LIMIT 1
        SET deleted_e.from = deleted_from
        WITH node_with_dup_edges, edge_type, edge_branch, peer
        MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        WITH deleted_e
        ORDER BY elementId(deleted_e)
        SKIP 1
        DELETE deleted_e
    }
}
"""
