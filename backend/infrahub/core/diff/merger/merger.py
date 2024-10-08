from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.query.merge import DiffMergePropertiesQuery, DiffMergeQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .serializer import DiffMergeSerializer


class DiffMerger:
    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_repository: DiffRepository,
        serializer: DiffMergeSerializer,
    ):
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.db = db
        self.diff_repository = diff_repository
        self.serializer = serializer

    async def merge_graph(self, at: Timestamp) -> None:
        enriched_diff = await self.diff_repository.get_one(
            diff_branch_name=self.source_branch.name, tracking_id=BranchTrackingId(name=self.source_branch.name)
        )
        async for node_diff_dicts, property_diff_dicts in self.serializer.serialize_diff(diff=enriched_diff):
            merge_query = await DiffMergeQuery.init(
                db=self.db,
                branch=self.source_branch,
                at=at,
                target_branch=self.destination_branch,
                node_diff_dicts=node_diff_dicts,
            )
            await merge_query.execute(db=self.db)
            merge_properties_query = await DiffMergePropertiesQuery.init(
                db=self.db,
                branch=self.source_branch,
                at=at,
                target_branch=self.destination_branch,
                property_diff_dicts=property_diff_dicts,
            )
            await merge_properties_query.execute(db=self.db)

        self.source_branch.branched_from = at.to_string()
        await self.source_branch.save(db=self.db)
