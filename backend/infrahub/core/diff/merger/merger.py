from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.query.bulk_merge import (
    BulkMergeAttributePropertyEdgesQuery,
    BulkMergeCardinalityOneResolutionQuery,
    BulkMergeNodeExistenceQuery,
    BulkMergeRelationshipEdgesQuery,
    BulkMergeRelationshipPropertyEdgesQuery,
)
from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
from infrahub.core.diff.query.merge import DiffMergeMetadataQuery
from infrahub.core.query.rollback import RollbackQuery
from infrahub.database import retry_db_transaction
from infrahub.log import get_logger

from .exclusion_plan import MergeExclusionPlan

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .exclusion_plan import MergeExclusionPlanBuilder

log = get_logger()


class DiffMerger:
    """Merges a source branch into a target branch (default branch only).

    1. Loads the enriched diff and builds a path-level merge exclusion plan from conflicts.
    2. Runs bulk Cypher merge queries that read source-branch edges, applying the exclusion
       plan so that BASE-resolved conflicts are skipped and DIFF-resolved cardinality-one
       rel conflicts get explicit cleanup of base-only peers.
    3. Updates metadata and supports rollback.
    """

    metadata_batch_size = 500

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_repository: DiffRepository,
        exclusion_plan_builder: MergeExclusionPlanBuilder,
    ) -> None:
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.db = db
        self.diff_repository = diff_repository
        self.exclusion_plan_builder = exclusion_plan_builder
        self._affected_node_uuids: list[str] = []

    async def merge_graph(self, at: Timestamp) -> None:
        tracking_id = BranchTrackingId(name=self.source_branch.name)

        log.info("Querying conflicted node UUIDs")
        conflict_uuids = await self.diff_repository.get_conflicted_node_uuids(
            diff_branch_name=self.source_branch.name,
            tracking_id=tracking_id,
        )
        if conflict_uuids:
            log.info(f"Loading enriched diff for {len(conflict_uuids)} conflicted node(s)")
            enriched_diff = await self.diff_repository.get_one(
                diff_branch_name=self.source_branch.name,
                tracking_id=tracking_id,
                filters=EnrichedDiffQueryFilters(ids=list(conflict_uuids)),
            )
            plan = self.exclusion_plan_builder.build(diff=enriched_diff)
        else:
            plan = MergeExclusionPlan()
        log.info(
            "Merge exclusion plan built",
            excluded_nodes=len(plan.excluded_node_uuids),
            excluded_attr_props=len(plan.excluded_attribute_property_paths),
            excluded_rels=len(plan.excluded_relationship_paths),
            excluded_rel_props=len(plan.excluded_relationship_property_paths),
            cardinality_one_diff_resolutions=len(plan.cardinality_one_diff_resolutions),
            carry_over_base_rel_props=len(plan.carry_over_base_relationship_properties),
            carry_over_diff_rel_props=len(plan.carry_over_diff_relationship_properties),
        )

        log.info("Running bulk node existence merge")
        await self._bulk_merge_node_existence(at=at, plan=plan)

        log.info("Running bulk relationship edge merge")
        await self._bulk_merge_relationship_edges(at=at, plan=plan)

        log.info("Running bulk cardinality-one resolution merge")
        await self._bulk_merge_cardinality_one_resolution(at=at, plan=plan)

        log.info("Running bulk attribute property edge merge")
        await self._bulk_merge_attribute_property_edges(at=at, plan=plan)

        log.info("Running bulk relationship property edge merge")
        await self._bulk_merge_relationship_property_edges(at=at, plan=plan)

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

        branched_from = at.subtract(microseconds=1)
        self.source_branch.branched_from = branched_from.to_string()
        await self.source_branch.save(db=self.db)
        registry.branch[self.source_branch.name] = self.source_branch

        log.info("Graph merge complete")

    @retry_db_transaction(name="bulk_merge_node_existence")
    async def _bulk_merge_node_existence(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        query = await BulkMergeNodeExistenceQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_node_uuids=plan.excluded_node_uuids,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_relationship_edges")
    async def _bulk_merge_relationship_edges(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        query = await BulkMergeRelationshipEdgesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_node_uuids=plan.excluded_node_uuids,
            excluded_relationship_paths=plan.excluded_relationship_paths,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_cardinality_one_resolution")
    async def _bulk_merge_cardinality_one_resolution(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        if (
            not plan.cardinality_one_diff_resolutions
            and not plan.carry_over_base_relationship_properties
            and not plan.carry_over_diff_relationship_properties
        ):
            log.info("No cardinality-one resolutions or relationship properties to carry over, skipping this step")
            return
        query = await BulkMergeCardinalityOneResolutionQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            cardinality_one_diff_resolutions=plan.cardinality_one_diff_resolutions,
            carry_over_base_relationship_properties=plan.carry_over_base_relationship_properties,
            carry_over_diff_relationship_properties=plan.carry_over_diff_relationship_properties,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_attribute_property_edges")
    async def _bulk_merge_attribute_property_edges(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        query = await BulkMergeAttributePropertyEdgesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_node_uuids=plan.excluded_node_uuids,
            excluded_attribute_property_paths=plan.excluded_attribute_property_paths,
        )
        await query.execute(db=self.db)

    @retry_db_transaction(name="bulk_merge_relationship_property_edges")
    async def _bulk_merge_relationship_property_edges(self, at: Timestamp, plan: MergeExclusionPlan) -> None:
        query = await BulkMergeRelationshipPropertyEdgesQuery.init(
            db=self.db,
            branch=self.source_branch,
            at=at,
            target_branch=self.destination_branch,
            excluded_node_uuids=plan.excluded_node_uuids,
            excluded_relationship_paths=plan.excluded_relationship_paths,
            excluded_relationship_property_paths=plan.excluded_relationship_property_paths,
        )
        await query.execute(db=self.db)

    async def rollback(self, at: Timestamp) -> None:
        if not self._affected_node_uuids:
            return
        rollback_query = await RollbackQuery.init(
            db=self.db,
            branch=self.source_branch,
            target_branch=self.destination_branch,
            at=at,
            node_uuids=self._affected_node_uuids,
        )
        await rollback_query.execute(db=self.db)
