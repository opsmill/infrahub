from typing import Any

from infrahub.core.diff.model.path import BranchTrackingId, FrozenTrackingId
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffFreezeByBranchQuery(Query):
    """Freezes DiffRoot nodes and their partners for a given branch.

    Sets is_frozen=TRUE and updates tracking_id to 'frozen.{branch_name}'
    for all unfrozen DiffRoots with a BranchTrackingId matching the branch name,
    as well as their partner DiffRoots.
    """

    name = "enriched_diff_freeze_by_branch"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        branch_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.branch_name = branch_name

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_tracking_id = BranchTrackingId(name=self.branch_name)
        frozen_tracking_id = FrozenTrackingId(name=self.branch_name)
        self.params = {
            "branch_tracking_id": branch_tracking_id.serialize(),
            "frozen_tracking_id": frozen_tracking_id.serialize(),
        }
        query = """
MATCH (diff_root:DiffRoot)
WHERE diff_root.tracking_id = $branch_tracking_id
AND (diff_root.is_frozen IS NULL OR diff_root.is_frozen <> TRUE)
OPTIONAL MATCH (diff_root)-[:DIFF_HAS_PARTNER]-(partner:DiffRoot)
SET diff_root.is_frozen = TRUE
SET diff_root.tracking_id = $frozen_tracking_id
SET partner.is_frozen = TRUE
SET partner.tracking_id = $frozen_tracking_id
        """
        self.add_to_query(query)
