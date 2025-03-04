from typing import Any

from neo4j.graph import Node as Neo4jNode

from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffConflictUpdateQuery(Query):
    name = "enriched_diff_conflict_update"
    type = QueryType.WRITE

    def __init__(
        self,
        conflict_id: str,
        selection: ConflictSelection | None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.conflict_id = conflict_id
        self.selection = selection

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {"conflict_id": self.conflict_id, "selection": self.selection.value if self.selection else None}
        query = """
        MATCH (conflict:DiffConflict {uuid: $conflict_id})
        SET conflict.selected_branch = $selection
        """
        self.return_labels = ["conflict"]
        self.add_to_query(query=query)

    async def get_conflict_node(self) -> Neo4jNode | None:
        result = self.get_result()
        if not result:
            return None
        return result.get_node("conflict")
