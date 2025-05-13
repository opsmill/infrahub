from collections import defaultdict
from dataclasses import asdict
from typing import AsyncGenerator

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import VertexToAdd


class PatchPlanVertexAdder:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_add_query(self, labels: list[str], vertices_to_add: list[VertexToAdd]) -> dict[str, str]:
        labels_str = ":".join(labels)
        serial_vertices_to_add: list[dict[str, str | int | bool]] = [asdict(v) for v in vertices_to_add]
        query = """
UNWIND $vertices_to_add AS vertex_to_add
CREATE (v:%(labels)s)
SET v = vertex_to_add.after_props
RETURN vertex_to_add.identifier AS abstract_id, %(id_func_name)s(v) AS db_id
        """ % {
            "labels": labels_str,
            "id_func_name": self.db.get_id_function_name(),
        }
        # use transaction to make sure we record the results before committing them
        try:
            txn_db = self.db.start_transaction()
            async with txn_db as txn:
                results = await txn.execute_query(
                    query=query, params={"vertices_to_add": serial_vertices_to_add}, type=QueryType.WRITE
                )
                abstract_to_concrete_id_map: dict[str, str] = {}
                for result in results:
                    abstract_id = result.get("abstract_id")
                    concrete_id = result.get("db_id")
                    abstract_to_concrete_id_map[abstract_id] = concrete_id
        finally:
            await txn_db.close()
        return abstract_to_concrete_id_map

    async def execute(self, vertices_to_add: list[VertexToAdd]) -> AsyncGenerator[dict[str, str], None]:
        """
        Create vertices_to_add on the database.
        Returns a generator that yields dictionaries mapping VertexToAdd.identifier to the database-level ID of the newly created vertex.
        """
        vertices_map_queue: dict[frozenset[str], list[VertexToAdd]] = defaultdict(list)
        for vertex_to_add in vertices_to_add:
            frozen_labels = frozenset(vertex_to_add.labels)
            vertices_map_queue[frozen_labels].append(vertex_to_add)
            if len(vertices_map_queue[frozen_labels]) > self.batch_size_limit:
                yield await self._run_add_query(
                    labels=list(frozen_labels),
                    vertices_to_add=vertices_map_queue[frozen_labels],
                )
                vertices_map_queue[frozen_labels] = []

        for frozen_labels, vertices_group in vertices_map_queue.items():
            yield await self._run_add_query(labels=list(frozen_labels), vertices_to_add=vertices_group)
