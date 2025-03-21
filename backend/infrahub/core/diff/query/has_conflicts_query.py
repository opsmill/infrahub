from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import BranchTrackingId


class EnrichedDiffHasConflictQuery(Query):
    name = "enriched_diff_has_conflicts"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: BranchTrackingId | None = None,
        diff_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if (diff_id is None and tracking_id is None) or (diff_id and tracking_id):
            raise ValueError("EnrichedDiffHasConflictQuery requires one and only one of `tracking_id` or `diff_id`")
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id
        self.diff_id = diff_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
            "diff_id": self.diff_id,
        }
        query = """
MATCH (diff_root:DiffRoot)
WHERE (diff_root.is_merged IS NULL OR diff_root.is_merged <> TRUE)
AND (
    ($diff_id IS NOT NULL AND diff_root.uuid = $diff_id)
    OR ($tracking_id IS NOT NULL AND diff_root.tracking_id = $tracking_id AND diff_root.diff_branch = $diff_branch_name)
)
WITH (
    exists(
        (diff_root)-[:DIFF_HAS_NODE]->(:DiffNode)-[:DIFF_HAS_CONFLICT]->(:DiffConflict)
    ) OR exists(
        (diff_root)-[:DIFF_HAS_NODE]->(:DiffNode)
        -[:DIFF_HAS_ATTRIBUTE]->(:DiffAttribute)
        -[:DIFF_HAS_PROPERTY]->(:DiffProperty)
        -[:DIFF_HAS_CONFLICT]->(:DiffConflict)
    ) OR exists(
        (diff_root)-[:DIFF_HAS_NODE]->(:DiffNode)
        -[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)
        -[:DIFF_HAS_ELEMENT]->(:DiffRelationshipElement)
        -[:DIFF_HAS_CONFLICT]->(:DiffConflict)
    ) OR exists(
        (diff_root)-[:DIFF_HAS_NODE]->(:DiffNode)
        -[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)
        -[:DIFF_HAS_ELEMENT]->(:DiffRelationshipElement)
        -[:DIFF_HAS_PROPERTY]->(:DiffProperty)
        -[:DIFF_HAS_CONFLICT]->(:DiffConflict)
    )
) AS has_conflict
RETURN has_conflict
        """
        self.return_labels = ["has_conflict"]
        self.add_to_query(query=query)

    async def has_conflict(self) -> bool:
        result = self.get_result()
        return bool(result and result.get("has_conflict"))
