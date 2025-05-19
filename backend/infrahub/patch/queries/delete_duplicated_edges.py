from ..models import EdgeToDelete, EdgeToUpdate, PatchPlan
from .base import PatchQuery


class DeleteDuplicatedEdgesPatchQuery(PatchQuery):
    """
    For all Node vertices, find duplicated or overlapping edges of the same status, type, and branch to update and delete
    - one edge will be kept for each pair of nodes and a given status, type, and branch. it will be
        updated to have the earliest "from" and "to" times in this group
    - all the other duplicate/overlapping edges will be deleted
    """

    @property
    def name(self) -> str:
        return "delete-duplicated-edges"

    async def plan(self) -> PatchPlan:
        query = """
// ------------
// Find vertex pairs that have duplicate edges
// ------------
MATCH (node_with_dup_edges:Node)-[edge]-(peer)
WITH node_with_dup_edges, type(edge) AS edge_type, edge.status AS edge_status, edge.branch AS edge_branch, peer, count(*) AS num_dup_edges
WHERE num_dup_edges > 1
WITH DISTINCT node_with_dup_edges, edge_type, edge_branch, peer
CALL {
    // ------------
    // Get the earliest active and deleted edges for this branch
    // ------------
    WITH node_with_dup_edges, edge_type, edge_branch, peer
    OPTIONAL MATCH (node_with_dup_edges)-[active_edge {branch: edge_branch, status: "active"}]-(peer)
    WHERE type(active_edge) = edge_type
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_edge
    ORDER BY active_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, head(collect(active_edge.from)) AS active_from
    OPTIONAL MATCH (node_with_dup_edges)-[deleted_edge {branch: edge_branch, status: "deleted"}]-(peer)
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_edge
    ORDER BY deleted_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, head(collect(deleted_edge.from)) AS deleted_from
    // ------------
    // Plan one active edge update with correct from and to times
    // ------------
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_from
        OPTIONAL MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        WITH node_with_dup_edges, edge_type, edge_branch, peer, active_from, deleted_from, active_e
        ORDER BY %(id_func_name)s(active_e)
        LIMIT 1
        WITH active_e, properties(active_e) AS before_props, {from: active_from, to: deleted_from} AS prop_updates
        RETURN CASE
            WHEN active_e IS NOT NULL THEN [
                {
                    db_id: %(id_func_name)s(active_e), before_props: before_props, prop_updates: prop_updates
                }
            ]
            ELSE []
        END AS active_edges_to_update
    }
    // ------------
    // Plan deletes for all the other active edges of this type on this branch
    // ------------
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer
        OPTIONAL MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        WITH node_with_dup_edges, peer, active_e
        ORDER BY %(id_func_name)s(active_e)
        SKIP 1
        WITH CASE
            WHEN active_e IS NOT NULL THEN {
                db_id: %(id_func_name)s(active_e),
                from_id: %(id_func_name)s(startNode(active_e)),
                to_id: %(id_func_name)s(endNode(active_e)),
                edge_type: type(active_e),
                before_props: properties(active_e)
            }
            ELSE NULL
        END AS serialized_edge
        RETURN collect(serialized_edge) AS active_edges_to_delete
    }
    // ------------
    // Plan one deleted edge update with correct from time
    // ------------
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, deleted_from
        OPTIONAL MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        WITH node_with_dup_edges, edge_type, edge_branch, peer, deleted_from, deleted_e
        ORDER BY %(id_func_name)s(deleted_e)
        LIMIT 1
        WITH deleted_e, properties(deleted_e) AS before_props, {from: deleted_from} AS prop_updates
        RETURN CASE
            WHEN deleted_e IS NOT NULL THEN [
                {
                    db_id: %(id_func_name)s(deleted_e), before_props: before_props, prop_updates: prop_updates
                }
            ]
            ELSE []
        END AS deleted_edges_to_update
    }
    // ------------
    // Plan deletes for all the other deleted edges of this type on this branch
    // ------------
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer
        OPTIONAL MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        WITH node_with_dup_edges, peer, deleted_e
        ORDER BY %(id_func_name)s(deleted_e)
        SKIP 1
        WITH CASE
            WHEN deleted_e IS NOT NULL THEN {
                db_id: %(id_func_name)s(deleted_e),
                from_id: %(id_func_name)s(startNode(deleted_e)),
                to_id: %(id_func_name)s(endNode(deleted_e)),
                edge_type: type(deleted_e),
                before_props: properties(deleted_e)
            }
            ELSE NULL
        END AS serialized_edge

        RETURN collect(serialized_edge) AS deleted_edges_to_delete
    }
    RETURN
        active_edges_to_update + deleted_edges_to_update AS edges_to_update,
        active_edges_to_delete + deleted_edges_to_delete AS edges_to_delete
}
RETURN edges_to_update, edges_to_delete
        """ % {"id_func_name": self.db.get_id_function_name()}
        results = await self.db.execute_query(query=query)
        edges_to_delete: list[EdgeToDelete] = []
        edges_to_update: list[EdgeToUpdate] = []
        for result in results:
            for serial_edge_to_delete in result.get("edges_to_delete"):
                edge_to_delete = EdgeToDelete(**serial_edge_to_delete)
                edges_to_delete.append(edge_to_delete)
            for serial_edge_to_update in result.get("edges_to_update"):
                prop_updates = serial_edge_to_update["prop_updates"]
                if prop_updates:
                    serial_edge_to_update["after_props"] = serial_edge_to_update["before_props"] | prop_updates
                    del serial_edge_to_update["prop_updates"]
                edge_to_update = EdgeToUpdate(**serial_edge_to_update)
                edges_to_update.append(edge_to_update)
        return PatchPlan(
            name=self.name,
            edges_to_delete=edges_to_delete,
            edges_to_update=edges_to_update,
        )
