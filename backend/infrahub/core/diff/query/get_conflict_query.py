from typing import Any

from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffConflictQuery(Query):
    name = "enriched_diff_conflict"
    type = QueryType.READ

    def __init__(self, conflict_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.conflict_id = conflict_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {"conflict_id": self.conflict_id}
        query = "MATCH (conflict:DiffConflict {uuid: $conflict_id})"
        self.return_labels = ["conflict"]
        self.add_to_query(query=query)

    async def get_conflict_node(self) -> Neo4jNode | None:
        result = self.get_result()
        if not result:
            return None
        return result.get_node("conflict")
