from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import VertexToDelete


class PatchPlanVertexDeleter:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_delete_query(self, ids_to_delete: list[str]) -> None:
        query = """
MATCH (n)
WHERE elementId(n) IN $ids_to_delete
DETACH DELETE n
        """
        await self.db.execute_query_with_metadata(
            query=query, params={"ids_to_delete": ids_to_delete}, type=QueryType.WRITE
        )

    async def execute(self, vertices_to_delete: list[VertexToDelete]) -> None:
        for i in range(0, len(vertices_to_delete), self.batch_size_limit):
            vertices_slice = vertices_to_delete[i : i + self.batch_size_limit]
            ids_to_delete = [v.db_id for v in vertices_slice]
            await self._run_delete_query(ids_to_delete=ids_to_delete)
