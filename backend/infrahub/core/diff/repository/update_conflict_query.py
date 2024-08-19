from typing import Any

from infrahub.core.diff.model.path import ConflictSelection, EnrichedDiffConflict
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from .deserializer import EnrichedDiffDeserializer


class EnrichedDiffConflictUpdateQuery(Query):
    name = "enriched_diff_conflict_update"
    type = QueryType.WRITE

    def __init__(
        self,
        deserializer: EnrichedDiffDeserializer,
        conflict_id: str,
        selection: ConflictSelection | None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.deserializer = deserializer
        self.conflict_id = conflict_id
        self.selection = selection

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {"conflict_id": self.conflict_id, "selection": self.selection.value if self.selection else None}
        query = """
        MATCH (conflict:DiffConflict {uuid: $conflict_id})
        SET conflict.selected_branch = $selection
        """
        self.return_labels = ["conflict"]
        self.add_to_query(query=query)

    async def get_conflict(self) -> EnrichedDiffConflict | None:
        result = self.get_result()
        if not result:
            return None
        return self.deserializer.deserialize_conflict(diff_conflict_node=result.get_node("conflict"))
