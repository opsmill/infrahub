from dataclasses import asdict

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import VertexToUpdate


class PatchPlanVertexUpdater:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_update_query(self, vertices_to_update: list[VertexToUpdate]) -> None:
        query = """
UNWIND $vertices_to_update AS vertex_to_update
MATCH (n)
WHERE %(id_func_name)s(n) = vertex_to_update.db_id
SET n = vertex_to_update.after_props
        """ % {"id_func_name": self.db.get_id_function_name()}
        await self.db.execute_query(
            query=query, params={"vertices_to_update": [asdict(v) for v in vertices_to_update]}, type=QueryType.WRITE
        )

    async def execute(self, vertices_to_update: list[VertexToUpdate]) -> None:
        for i in range(0, len(vertices_to_update), self.batch_size_limit):
            vertices_slice = vertices_to_update[i : i + self.batch_size_limit]
            await self._run_update_query(vertices_to_update=vertices_slice)
