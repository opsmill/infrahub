# consolidate duplicated nodes
query = """
MATCH (n:Node)
WITH n.uuid AS node_uuid, count(*) as num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
WITH DISTINCT node_uuid
MATCH (n:Node {uuid: node_uuid})
CALL {
    WITH n
    WITH labels(n) AS n_labels
    UNWIND n_labels AS n_label
    WITH n_label
    ORDER BY n_label ASC
    RETURN collect(n_label) AS sorted_labels
}
WITH n.uuid AS n_uuid, sorted_labels, collect(n) AS duplicate_nodes
WHERE size(duplicate_nodes) > 1
WITH n_uuid, head(duplicate_nodes) AS node_to_keep, tail(duplicate_nodes) AS nodes_to_delete
UNWIND nodes_to_delete AS node_to_delete
//------------
// Repeat for both directions of IS_RELATED
//------------
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)-[edge_to_move:HAS_ATTRIBUTE]->(peer)
    CREATE (node_to_keep)-[new_edge:HAS_ATTRIBUTE]->(peer)
    SET new_edge = edge_to_move
    DELETE edge_to_move
}
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)-[edge_to_move:IS_RELATED]->(peer)
    CREATE (node_to_keep)-[new_edge:IS_RELATED]->(peer)
    SET new_edge = edge_to_move
    DELETE edge_to_move
}
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)<-[edge_to_move:IS_RELATED]-(peer)
    CREATE (node_to_keep)<-[new_edge:IS_RELATED]-(peer)
    SET new_edge = edge_to_move
    DELETE edge_to_move
}
DETACH DELETE node_to_delete
"""

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

# add missing IS_PART_OF edges

query = """
// nodes missing IS_PART_OF edges
MATCH (n:Node)
WHERE NOT exists((n)-[:IS_PART_OF]->(:Root))
CALL {
    WITH n
    // get each branch this node has edges on
    MATCH (n)-[e {status: "active"}]-()
    // for each branch, return the earliest active edge
    WITH DISTINCT n, active_e.branch AS branch
    MATCH (n)-[active_e {status: "active", branch: branch}]-()
    ORDER BY active_e.from ASC
    RETURN head(collect(active_e)) AS earliest_active, branch
}
CALL {
    WITH n
    // get each branch this node has edges on
    MATCH (n)-[attr_edge:HAS_ATTRIBUTE]->()
    WITH DISTINCT n, attr_edge.branch AS branch

    
}
"""
