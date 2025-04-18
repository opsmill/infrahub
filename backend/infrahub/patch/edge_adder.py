from collections import defaultdict
from dataclasses import asdict

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import EdgeToAdd


class PatchPlanEdgeAdder:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_add_query(self, edge_type: str, edges_to_add: list[EdgeToAdd]) -> None:
        query = """
UNWIND $edges_to_add AS edge_to_add
MATCH (a) WHERE elementId(a) = edge_to_add.from_id
MATCH (b) WHERE elementId(b) = edge_to_add.to_id
CALL {
    WITH a, b, edge_to_add
    OPTIONAL MATCH (a)-[e:%(edge_type)s]->(b)
    RETURN (e IS NOT NULL AND properties(e) = edge_to_add.after_props) AS edge_exists
    ORDER BY edge_exists DESC
    LIMIT 1
}
WITH a, b, edge_to_add, edge_exists
WHERE NOT edge_exists
CREATE (a)-[new_edge:%(edge_type)s]->(b)
SET new_edge = edge_to_add.after_props
RETURN new_edge
        """ % {"edge_type": edge_type}
        edges_to_add_dicts = [asdict(v) for v in edges_to_add]
        await self.db.execute_query_with_metadata(
            query=query, params={"edges_to_add": edges_to_add_dicts}, type=QueryType.WRITE
        )

    async def execute(
        self,
        edges_to_add: list[EdgeToAdd],
    ) -> None:
        edges_map_queue: dict[str, list[EdgeToAdd]] = defaultdict(list)
        for edge_to_add in edges_to_add:
            edges_map_queue[edge_to_add.edge_type].append(edge_to_add)
            if len(edges_map_queue[edge_to_add.edge_type]) > self.batch_size_limit:
                await self._run_add_query(
                    edge_type=edge_to_add.edge_type,
                    edges_to_add=edges_map_queue[edge_to_add.edge_type],
                )
                edges_map_queue[edge_to_add.edge_type] = []

        for edge_type, edges_group in edges_map_queue.items():
            await self._run_add_query(edge_type=edge_type, edges_to_add=edges_group)
