from ..models import EdgeToAdd, EdgeToDelete, PatchPlan, VertexToDelete
from .base import PatchQuery


class ConsolidateDuplicatedNodesPatchQuery(PatchQuery):
    @property
    def name(self) -> str:
        return "consolidate-duplicated-nodes"

    async def plan(self) -> PatchPlan:
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
    MATCH (node_to_delete)-[edge_to_delete]->(peer)
    RETURN {
        from_id: elementId(node_to_keep),
        to_id: elementId(peer),
        edge_type: type(edge_to_delete),
        after_props: properties(edge_to_delete)
    } AS edge_to_create
    UNION
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)<-[edge_to_delete]-(peer)
    RETURN {
        from_id: elementId(peer),
        to_id: elementId(node_to_keep),
        edge_type: type(edge_to_delete),
        after_props: properties(edge_to_delete)
    } AS edge_to_create
}
WITH node_to_delete, collect(edge_to_create) AS edges_to_create
CALL {
    WITH node_to_delete
    MATCH (node_to_delete)-[e]->(peer)
    RETURN {
        db_id: elementId(e),
        from_id: elementId(node_to_delete),
        to_id: elementId(peer),
        edge_type: type(e),
        before_props: properties(e)
    } AS edge_to_delete
    UNION
    WITH node_to_delete
    MATCH (node_to_delete)<-[e]-(peer)
    RETURN {
        db_id: elementId(e),
        from_id: elementId(peer),
        to_id: elementId(node_to_delete),
        edge_type: type(e),
        before_props: properties(e)
    } AS edge_to_delete
}
WITH node_to_delete, edges_to_create, collect(edge_to_delete) AS edges_to_delete
RETURN
    {db_id: elementId(node_to_delete), labels: labels(node_to_delete), before_props: properties(node_to_delete)} AS vertex_to_delete,
    edges_to_create,
    edges_to_delete
        """
        results = await self.db.execute_query(query=query)
        vertices_to_delete: list[VertexToDelete] = []
        edges_to_delete: list[EdgeToDelete] = []
        edges_to_add: list[EdgeToAdd] = []
        for result in results:
            serial_vertex_to_delete = result.get("vertex_to_delete")
            if serial_vertex_to_delete:
                vertex_to_delete = VertexToDelete(**serial_vertex_to_delete)
                vertices_to_delete.append(vertex_to_delete)
            for serial_edge_to_delete in result.get("edges_to_delete"):
                edge_to_delete = EdgeToDelete(**serial_edge_to_delete)
                edges_to_delete.append(edge_to_delete)
            for serial_edge_to_create in result.get("edges_to_create"):
                edges_to_add.append(EdgeToAdd(**serial_edge_to_create))
        return PatchPlan(
            name=self.name,
            vertices_to_delete=vertices_to_delete,
            edges_to_add=edges_to_add,
            edges_to_delete=edges_to_delete,
        )
