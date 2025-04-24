from ..models import EdgeToAdd, EdgeToDelete, PatchPlan, VertexToDelete
from .base import PatchQuery


class ConsolidateDuplicatedNodesPatchQuery(PatchQuery):
    """
    Find any groups of nodes with the same labels and properties, move all the edges to one of the duplicated nodes,
    then delete the other duplicated nodes
    """

    @property
    def name(self) -> str:
        return "consolidate-duplicated-nodes"

    async def plan(self) -> PatchPlan:
        query = """
//------------
// Find nodes with the same labels and UUID
//------------
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
// Find the edges that we need to move to the selected node_to_keep
//------------
CALL {
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)-[edge_to_delete]->(peer)
    RETURN {
        from_id: %(id_func_name)s(node_to_keep),
        to_id: %(id_func_name)s(peer),
        edge_type: type(edge_to_delete),
        after_props: properties(edge_to_delete)
    } AS edge_to_create
    UNION
    WITH node_to_keep, node_to_delete
    MATCH (node_to_delete)<-[edge_to_delete]-(peer)
    RETURN {
        from_id: %(id_func_name)s(peer),
        to_id: %(id_func_name)s(node_to_keep),
        edge_type: type(edge_to_delete),
        after_props: properties(edge_to_delete)
    } AS edge_to_create
}
WITH node_to_delete, collect(edge_to_create) AS edges_to_create
//------------
// Find the edges that we need to remove from the duplicated nodes
//------------
CALL {
    WITH node_to_delete
    MATCH (node_to_delete)-[e]->(peer)
    RETURN {
        db_id: %(id_func_name)s(e),
        from_id: %(id_func_name)s(node_to_delete),
        to_id: %(id_func_name)s(peer),
        edge_type: type(e),
        before_props: properties(e)
    } AS edge_to_delete
    UNION
    WITH node_to_delete
    MATCH (node_to_delete)<-[e]-(peer)
    RETURN {
        db_id: %(id_func_name)s(e),
        from_id: %(id_func_name)s(peer),
        to_id: %(id_func_name)s(node_to_delete),
        edge_type: type(e),
        before_props: properties(e)
    } AS edge_to_delete
}
WITH node_to_delete, edges_to_create, collect(edge_to_delete) AS edges_to_delete
RETURN
    {db_id: %(id_func_name)s(node_to_delete), labels: labels(node_to_delete), before_props: properties(node_to_delete)} AS vertex_to_delete,
    edges_to_create,
    edges_to_delete
        """ % {"id_func_name": self.db.get_id_function_name()}
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
