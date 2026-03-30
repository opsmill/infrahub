from typing import Any

from infrahub.core.diff.model.path import FrozenTrackingId
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffFreezeByProposedChangeQuery(Query):
    """Freezes DiffRoot nodes linked to a ProposedChange.

    Sets is_frozen=TRUE and updates tracking_id to 'frozen.{proposed_change_id}'
    for all DiffRoots linked via DIFF_FOR_PROPOSED_CHANGE relationship.
    """

    name = "enriched_diff_freeze_by_proposed_change"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        proposed_change_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.proposed_change_id = proposed_change_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        frozen_tracking_id = FrozenTrackingId(name=self.proposed_change_id)
        self.params = {
            "proposed_change_id": self.proposed_change_id,
            "frozen_tracking_id": frozen_tracking_id.serialize(),
        }
        query = """
MATCH (diff_root:DiffRoot)-[:DIFF_FOR_PROPOSED_CHANGE]->(pc:Node {uuid: $proposed_change_id})
SET diff_root.is_frozen = TRUE
SET diff_root.tracking_id = $frozen_tracking_id
        """
        self.add_to_query(query)
