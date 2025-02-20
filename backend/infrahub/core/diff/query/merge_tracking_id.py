from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import TrackingId


class EnrichedDiffMergedTrackingIdQuery(Query):
    name = "enriched_diff_merge_tracking_id"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, tracking_ids: list[TrackingId], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tracking_ids = tracking_ids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {"tracking_ids": [t_id.serialize() for t_id in self.tracking_ids]}
        query = """
        MATCH (d_root:DiffRoot)
        WHERE d_root.tracking_id IN $tracking_ids
        SET d_root.is_merged = TRUE
        """
        self.add_to_query(query=query)
