from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.query.merge import DiffMergePropertiesQuery, DiffMergeQuery, DiffMergeRollbackQuery
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .serializer import DiffMergeSerializer

log = get_logger()


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

    async def merge_graph(self, at: Timestamp) -> EnrichedDiffRoot:
        tracking_id = BranchTrackingId(name=self.source_branch.name)
        enriched_diffs = await self.diff_repository.get_roots_metadata(
            diff_branch_names=[self.source_branch.name],
            base_branch_names=[self.destination_branch.name],
            tracking_id=tracking_id,
        )
        latest_diff = None
        for diff in enriched_diffs:
            if latest_diff is None or (diff.to_time > latest_diff.to_time):
                latest_diff = diff
        if latest_diff is None:
            raise RuntimeError(f"Missing diff for branch {self.source_branch.name}")
        log.info(f"Retrieving diff {latest_diff.uuid}")
        enriched_diff = await self.diff_repository.get_one(
            diff_branch_name=self.source_branch.name, diff_id=latest_diff.uuid
        )
        log.info(f"Diff {latest_diff.uuid} retrieved")
        batch_num = 0
        async for node_diff_dicts, property_diff_dicts in self.serializer.serialize_diff(diff=enriched_diff):
            log.info(f"Merging batch of nodes #{batch_num}")
            merge_query = await DiffMergeQuery.init(
                db=self.db,
                branch=self.source_branch,
                at=at,
                target_branch=self.destination_branch,
                node_diff_dicts=node_diff_dicts,
            )
            await merge_query.execute(db=self.db)
            log.info(f"Merging batch of properties #{batch_num}")
            merge_properties_query = await DiffMergePropertiesQuery.init(
                db=self.db,
                branch=self.source_branch,
                at=at,
                target_branch=self.destination_branch,
                property_diff_dicts=property_diff_dicts,
            )
            await merge_properties_query.execute(db=self.db)
            log.info(f"Batch #{batch_num} merged")
            batch_num += 1

        self.source_branch.branched_from = at.to_string()
        await self.source_branch.save(db=self.db)
        registry.branch[self.source_branch.name] = self.source_branch
        return enriched_diff

    async def rollback(self, at: Timestamp) -> None:
        rollback_query = await DiffMergeRollbackQuery.init(
            db=self.db, branch=self.source_branch, target_branch=self.destination_branch, at=at
        )
        await rollback_query.execute(db=self.db)
