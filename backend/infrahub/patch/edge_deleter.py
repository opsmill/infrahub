from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import EdgeToDelete


class PatchPlanEdgeDeleter:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_delete_query(self, ids_to_delete: list[str]) -> None:
        query = """
MATCH ()-[e]-()
WHERE elementId(e) IN $ids_to_delete
DELETE e
        """
        await self.db.execute_query_with_metadata(
            query=query, params={"ids_to_delete": ids_to_delete}, type=QueryType.WRITE
        )

    async def execute(self, edges_to_delete: list[EdgeToDelete]) -> None:
        for i in range(0, len(edges_to_delete), self.batch_size_limit):
            edges_slice = edges_to_delete[i : i + self.batch_size_limit]
            ids_to_delete = [e.db_id for e in edges_slice]
            await self._run_delete_query(ids_to_delete=ids_to_delete)
