from collections import defaultdict
from dataclasses import asdict
from typing import AsyncGenerator

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import EdgeToAdd


class PatchPlanEdgeAdder:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_add_query(self, edge_type: str, edges_to_add: list[EdgeToAdd]) -> dict[str, str]:
        query = """
UNWIND $edges_to_add AS edge_to_add
MATCH (a) WHERE %(id_func_name)s(a) = edge_to_add.from_id
MATCH (b) WHERE %(id_func_name)s(b) = edge_to_add.to_id
CREATE (a)-[e:%(edge_type)s]->(b)
SET e = edge_to_add.after_props
RETURN edge_to_add.identifier AS abstract_id, %(id_func_name)s(e) AS db_id
        """ % {
            "edge_type": edge_type,
            "id_func_name": self.db.get_id_function_name(),
        }
        edges_to_add_dicts = [asdict(v) for v in edges_to_add]
        # use transaction to make sure we record the results before committing them
        try:
            txn_db = self.db.start_transaction()
            async with txn_db as txn:
                results = await txn.execute_query(
                    query=query, params={"edges_to_add": edges_to_add_dicts}, type=QueryType.WRITE
                )
            abstract_to_concrete_id_map: dict[str, str] = {}
            for result in results:
                abstract_id = result.get("abstract_id")
                concrete_id = result.get("db_id")
                abstract_to_concrete_id_map[abstract_id] = concrete_id
        finally:
            await txn_db.close()
        return abstract_to_concrete_id_map

    async def execute(
        self,
        edges_to_add: list[EdgeToAdd],
    ) -> AsyncGenerator[dict[str, str], None]:
        """
        Create edges_to_add on the database.
        Returns a generator that yields dictionaries mapping EdgeToAdd.identifier to the database-level ID of the newly created edge.
        """
        edges_map_queue: dict[str, list[EdgeToAdd]] = defaultdict(list)
        for edge_to_add in edges_to_add:
            edges_map_queue[edge_to_add.edge_type].append(edge_to_add)
            if len(edges_map_queue[edge_to_add.edge_type]) > self.batch_size_limit:
                yield await self._run_add_query(
                    edge_type=edge_to_add.edge_type,
                    edges_to_add=edges_map_queue[edge_to_add.edge_type],
                )
                edges_map_queue[edge_to_add.edge_type] = []

        for edge_type, edges_group in edges_map_queue.items():
            yield await self._run_add_query(edge_type=edge_type, edges_to_add=edges_group)
