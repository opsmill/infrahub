from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.query.merge import (
    DiffMergeMetadataQuery,
    DiffMergeMigratedKindsQuery,
    DiffMergePropertiesQuery,
    DiffMergeQuery,
    DiffMergeRollbackQuery,
)
from infrahub.database import retry_db_transaction
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
    metadata_batch_size = 500

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_repository: DiffRepository,
        serializer: DiffMergeSerializer,
    ) -> None:
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.db = db
        self.diff_repository = diff_repository
        self.serializer = serializer
        self._affected_node_uuids: list[str] = []

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
        migrated_kinds_id_map = {}
        for n in enriched_diff.nodes:
            if not n.is_node_kind_migration:
                continue
            if n.uuid not in migrated_kinds_id_map or (
                n.uuid in migrated_kinds_id_map and n.action is DiffAction.ADDED
            ):
                # make sure that we use the ADDED db_id if it exists
                # it will not if a node was migrated and then deleted
                migrated_kinds_id_map[n.uuid] = n.identifier.db_id

        async for node_diff_dicts, property_diff_dicts in self.serializer.serialize_diff(diff=enriched_diff):
            if node_diff_dicts:
                log.info(f"Merging batch of nodes #{batch_num}")
                await self._merge_nodes(
                    at=at, node_diff_dicts=node_diff_dicts, migrated_kinds_id_map=migrated_kinds_id_map
                )
            if property_diff_dicts:
                log.info(f"Merging batch of properties #{batch_num}")
                await self._merge_properties(
                    at=at, property_diff_dicts=property_diff_dicts, migrated_kinds_id_map=migrated_kinds_id_map
                )
            log.info(f"Batch #{batch_num} merged")
            batch_num += 1
        migrated_kind_uuids = {n.identifier.uuid for n in enriched_diff.nodes if n.is_node_kind_migration}
        if migrated_kind_uuids:
            migrated_merge_query = await DiffMergeMigratedKindsQuery.init(
                db=self.db,
                branch=self.source_branch,
                at=at,
                target_branch=self.destination_branch,
                migrated_uuids=list(migrated_kind_uuids),
            )
            await migrated_merge_query.execute(db=self.db)

        affected_node_uuids = [n.uuid for n in enriched_diff.nodes]
        self._affected_node_uuids = affected_node_uuids
        if affected_node_uuids:
            for i in range(0, len(affected_node_uuids), self.metadata_batch_size):
                batch_uuids = affected_node_uuids[i : i + self.metadata_batch_size]
                log.info(f"Updating metadata for batch {i // self.metadata_batch_size + 1} ({len(batch_uuids)} nodes)")
                metadata_query = await DiffMergeMetadataQuery.init(
                    db=self.db,
                    branch=self.source_branch,
                    at=at,
                    target_branch=self.destination_branch,
                    node_uuids=batch_uuids,
                )
                await metadata_query.execute(db=self.db)

        # set the branched_from time to the previous microsecond to prevent duplicated
        # relationships on the branch after the merge
        branched_from = at.subtract(microseconds=1)

        self.source_branch.branched_from = branched_from.to_string()
        await self.source_branch.save(db=self.db)
        registry.branch[self.source_branch.name] = self.source_branch
        return enriched_diff

    @retry_db_transaction(name="diff_merge_nodes")
    async def _merge_nodes(
        self, at: Timestamp, node_diff_dicts: list[dict], migrated_kinds_id_map: dict[str, str]
    ) -> None:
        merge_query = await DiffMergeQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            node_diff_dicts=node_diff_dicts,
            migrated_kinds_id_map=migrated_kinds_id_map,
        )
        await merge_query.execute(db=self.db)

    @retry_db_transaction(name="diff_merge_properties")
    async def _merge_properties(
        self, at: Timestamp, property_diff_dicts: list[dict], migrated_kinds_id_map: dict[str, str]
    ) -> None:
        merge_properties_query = await DiffMergePropertiesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            property_diff_dicts=property_diff_dicts,
            migrated_kinds_id_map=migrated_kinds_id_map,
        )
        await merge_properties_query.execute(db=self.db)

    async def rollback(self, at: Timestamp) -> None:
        if not self._affected_node_uuids:
            return
        rollback_query = await DiffMergeRollbackQuery.init(
            db=self.db,
            branch=self.source_branch,
            target_branch=self.destination_branch,
            at=at,
            node_uuids=self._affected_node_uuids,
        )
        await rollback_query.execute(db=self.db)
