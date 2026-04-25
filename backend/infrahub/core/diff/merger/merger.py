from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.query.bulk_merge import (
    BulkMergeAttributePropertyEdgesQuery,
    BulkMergeNodeExistenceQuery,
    BulkMergeRelationshipEdgesQuery,
    BulkMergeRelationshipPropertyEdgesQuery,
)
from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
from infrahub.core.diff.query.merge import (
    DiffMergeMetadataQuery,
    DiffMergePropertiesQuery,
    DiffMergeQuery,
    DiffMergeRollbackQuery,
)
from infrahub.database import retry_db_transaction
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .serializer import DiffMergeSerializer

log = get_logger()


class DiffMerger:
    """Merges a source branch into a target branch (default branch only)

    1. Queries the diff graph for conflict UUIDs
    2. Runs bulk Cypher merge queries that discover changes from data-graph edge properties
    3. Handles conflicted nodes via the existing DiffMergeSerializer fallback path
    4. Updates metadata and supports rollback
    """

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

    async def merge_graph(self, at: Timestamp) -> None:
        tracking_id = BranchTrackingId(name=self.source_branch.name)

        # ------------------------------------------------------------------
        # Step 1: Query the diff graph for conflict UUIDs
        # ------------------------------------------------------------------
        log.info("Querying diff graph for merge exclusions")
        conflict_uuids = await self.diff_repository.get_conflicted_node_uuids(
            diff_branch_name=self.source_branch.name,
            tracking_id=tracking_id,
        )
        excluded_uuids = list(conflict_uuids)
        log.info(f"Merge exclusions: {len(conflict_uuids)} conflicted")

        # ------------------------------------------------------------------
        # Step 2: Run bulk Cypher merge queries (excludes only conflicted nodes)
        # ------------------------------------------------------------------
        log.info("Running bulk node existence merge")
        await self._bulk_merge_node_existence(at=at, excluded_uuids=excluded_uuids)

        log.info("Running bulk relationship edge merge")
        await self._bulk_merge_relationship_edges(at=at, excluded_uuids=excluded_uuids)

        log.info("Running bulk attribute property edge merge")
        await self._bulk_merge_attribute_property_edges(at=at, excluded_uuids=excluded_uuids)

        log.info("Running bulk relationship property edge merge")
        await self._bulk_merge_relationship_property_edges(at=at, excluded_uuids=excluded_uuids)

        # ------------------------------------------------------------------
        # Step 3: Handle conflicted nodes via existing serializer path
        # ------------------------------------------------------------------
        if conflict_uuids:
            log.info(f"Handling {len(conflict_uuids)} conflicted nodes via fallback path")
            await self._run_merge_fallback(
                at=at,
                conflict_uuids=conflict_uuids,
                tracking_id=tracking_id,
            )

        # ------------------------------------------------------------------
        # Step 4: Discover affected node UUIDs and update metadata
        # ------------------------------------------------------------------
        log.info("Discovering affected node UUIDs for metadata update")
        affected_node_uuids = await self.diff_repository.get_affected_node_uuids(
            source_branch=self.source_branch,
            target_branch=self.destination_branch,
            at=at,
            tracking_id=tracking_id,
        )
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

        # ------------------------------------------------------------------
        # Step 5: Update source branch branched_from timestamp
        # ------------------------------------------------------------------
        branched_from = at.subtract(microseconds=1)
        self.source_branch.branched_from = branched_from.to_string()
        await self.source_branch.save(db=self.db)
        registry.branch[self.source_branch.name] = self.source_branch

        log.info("Graph merge complete")

    @retry_db_transaction(name="bulk_merge_node_existence")
    async def _bulk_merge_node_existence(self, at: Timestamp, excluded_uuids: list[str]) -> None:
        query = await BulkMergeNodeExistenceQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_uuids=excluded_uuids,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_attribute_property_edges")
    async def _bulk_merge_attribute_property_edges(self, at: Timestamp, excluded_uuids: list[str]) -> None:
        query = await BulkMergeAttributePropertyEdgesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_uuids=excluded_uuids,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_relationship_property_edges")
    async def _bulk_merge_relationship_property_edges(self, at: Timestamp, excluded_uuids: list[str]) -> None:
        query = await BulkMergeRelationshipPropertyEdgesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_uuids=excluded_uuids,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_relationship_edges")
    async def _bulk_merge_relationship_edges(self, at: Timestamp, excluded_uuids: list[str]) -> None:
        query = await BulkMergeRelationshipEdgesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_uuids=excluded_uuids,
        )
        await query.execute(db=self.db)

    async def _run_merge_fallback(
        self,
        at: Timestamp,
        conflict_uuids: set[str],
        tracking_id: BranchTrackingId,
    ) -> None:
        """Load conflicted nodes from the diff and merge them via the old serializer path."""
        enriched_diff = await self.diff_repository.get_one(
            diff_branch_name=self.source_branch.name,
            tracking_id=tracking_id,
            filters=EnrichedDiffQueryFilters(ids=list(conflict_uuids)),
        )

        # migrated_kinds_id_map is empty — migrated nodes are handled by bulk queries
        migrated_kinds_id_map: dict[str, str] = {}

        batch_num = 0
        async for node_diff_dicts, property_diff_dicts in self.serializer.serialize_diff(diff=enriched_diff):
            if node_diff_dicts:
                log.info(f"Merging fallback node batch #{batch_num}")
                await self._merge_nodes_fallback(
                    at=at, node_diff_dicts=node_diff_dicts, migrated_kinds_id_map=migrated_kinds_id_map
                )
            if property_diff_dicts:
                log.info(f"Merging fallback property batch #{batch_num}")
                await self._merge_properties_fallback(
                    at=at, property_diff_dicts=property_diff_dicts, migrated_kinds_id_map=migrated_kinds_id_map
                )
            batch_num += 1

    @retry_db_transaction(name="merge_fallback_nodes")
    async def _merge_nodes_fallback(
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

    @retry_db_transaction(name="merge_fallback_properties")
    async def _merge_properties_fallback(
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
