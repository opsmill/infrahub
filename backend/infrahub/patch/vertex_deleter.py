from typing import AsyncGenerator

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import VertexToDelete


class PatchPlanVertexDeleter:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_delete_query(self, ids_to_delete: list[str]) -> set[str]:
        query = """
MATCH (n)
WHERE %(id_func_name)s(n) IN $ids_to_delete
DETACH DELETE n
RETURN %(id_func_name)s(n) AS deleted_id
        """ % {"id_func_name": self.db.get_id_function_name()}
        results = await self.db.execute_query(
            query=query, params={"ids_to_delete": ids_to_delete}, type=QueryType.WRITE
        )
        deleted_ids: set[str] = set()
        for result in results:
            deleted_id = result.get("deleted_id")
            deleted_ids.add(deleted_id)
        return deleted_ids

    async def execute(self, vertices_to_delete: list[VertexToDelete]) -> AsyncGenerator[set[str], None]:
        for i in range(0, len(vertices_to_delete), self.batch_size_limit):
            ids_to_delete = [v.db_id for v in vertices_to_delete[i : i + self.batch_size_limit]]
            yield await self._run_delete_query(ids_to_delete=ids_to_delete)
