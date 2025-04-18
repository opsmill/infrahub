from dataclasses import asdict

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase

from .models import EdgeToUpdate


class PatchPlanEdgeUpdater:
    def __init__(self, db: InfrahubDatabase, batch_size_limit: int = 1000) -> None:
        self.db = db
        self.batch_size_limit = batch_size_limit

    async def _run_update_query(self, edges_to_update: list[EdgeToUpdate]) -> None:
        query = """
UNWIND $edges_to_update AS edge_to_update
MATCH ()-[e]-()
WHERE elementId(e) = edge_to_update.db_id
SET e = edge_to_update.after_props
        """
        await self.db.execute_query_with_metadata(
            query=query, params={"edges_to_update": [asdict(e) for e in edges_to_update]}, type=QueryType.WRITE
        )

    async def execute(self, edges_to_update: list[EdgeToUpdate]) -> None:
        for i in range(0, len(edges_to_update), self.batch_size_limit):
            vertices_slice = edges_to_update[i : i + self.batch_size_limit]
            await self._run_update_query(edges_to_update=vertices_slice)
