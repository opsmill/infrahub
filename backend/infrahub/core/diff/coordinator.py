from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable
from uuid import uuid4

from infrahub import lock
from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

from .model.path import (
    BranchTrackingId,
    EnrichedDiffRoot,
    EnrichedDiffRootEmpty,
    EnrichedDiffs,
    EnrichedDiffsEmpty,
    NameTrackingId,
    NodeFieldSpecifier,
    TrackingId,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node

    from .calculator import DiffCalculator
    from .combiner import DiffCombiner
    from .conflict_transferer import DiffConflictTransferer
    from .conflicts_enricher import ConflictsEnricher
    from .data_check_synchronizer import DiffDataCheckSynchronizer
    from .enricher.aggregated import AggregatedDiffEnricher
    from .enricher.labels import DiffLabelsEnricher
    from .enricher.summary_counts import DiffSummaryCountsEnricher
    from .repository.repository import DiffRepository


log = get_logger()


@dataclass
class EnrichedDiffRequest:
    base_branch: Branch
    diff_branch: Branch
    from_time: Timestamp
    to_time: Timestamp
    node_field_specifiers: set[NodeFieldSpecifier] = field(default_factory=set)


class DiffCoordinator:
    lock_namespace = "diff-update"

    def __init__(
        self,
        diff_repo: DiffRepository,
        diff_calculator: DiffCalculator,
        diff_enricher: AggregatedDiffEnricher,
        diff_combiner: DiffCombiner,
        conflicts_enricher: ConflictsEnricher,
        labels_enricher: DiffLabelsEnricher,
        summary_counts_enricher: DiffSummaryCountsEnricher,
        data_check_synchronizer: DiffDataCheckSynchronizer,
        conflict_transferer: DiffConflictTransferer,
    ) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_enricher = diff_enricher
        self.diff_combiner = diff_combiner
        self.conflicts_enricher = conflicts_enricher
        self.labels_enricher = labels_enricher
        self.summary_counts_enricher = summary_counts_enricher
        self.data_check_synchronizer = data_check_synchronizer
        self.conflict_transferer = conflict_transferer
        self.lock_registry = lock.registry

    async def run_update(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: str | None = None,
        to_time: str | None = None,
        name: str | None = None,
    ) -> None:
        # we are updating a diff that tracks the full lifetime of a branch
        if not name and not from_time and not to_time:
            await self.update_branch_diff(base_branch=base_branch, diff_branch=diff_branch)
            return

        if from_time:
            from_timestamp = Timestamp(from_time)
        else:
            from_timestamp = Timestamp(diff_branch.get_branched_from())
        if to_time:
            to_timestamp = Timestamp(to_time)
        else:
            to_timestamp = Timestamp()
        await self.create_or_update_arbitrary_timeframe_diff(
            base_branch=base_branch,
            diff_branch=diff_branch,
            from_time=from_timestamp,
            to_time=to_timestamp,
            name=name,
        )

    def _get_lock_name(self, base_branch_name: str, diff_branch_name: str, is_incremental: bool) -> str:
        lock_name = f"{base_branch_name}__{diff_branch_name}"
        if is_incremental:
            lock_name += "__incremental"
        return lock_name

    async def update_branch_diff_and_return(self, base_branch: Branch, diff_branch: Branch) -> EnrichedDiffRoot:
        enriched_diff = await self.update_branch_diff(base_branch=base_branch, diff_branch=diff_branch)
        if enriched_diff:
            return enriched_diff
        return await self.diff_repo.get_one(
            diff_branch_name=diff_branch.name, tracking_id=BranchTrackingId(name=diff_branch.name)
        )

    async def update_branch_diff(self, base_branch: Branch, diff_branch: Branch) -> EnrichedDiffRoot | None:
        log.info(f"Received request to update branch diff for {base_branch.name} - {diff_branch.name}")
        incremental_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=True
        )
        existing_incremental_lock = self.lock_registry.get_existing(
            name=incremental_lock_name, namespace=self.lock_namespace
        )
        if existing_incremental_lock and await existing_incremental_lock.locked():
            log.info(f"Branch diff update for {base_branch.name} - {diff_branch.name} already in progress")
            async with self.lock_registry.get(name=incremental_lock_name, namespace=self.lock_namespace):
                log.info(f"Existing branch diff update for {base_branch.name} - {diff_branch.name} complete")
                return await self.diff_repo.get_one(
                    tracking_id=BranchTrackingId(name=diff_branch.name), diff_branch_name=diff_branch.name
                )
        general_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=False
        )
        from_time = Timestamp(diff_branch.get_branched_from())
        to_time = Timestamp()
        tracking_id = BranchTrackingId(name=diff_branch.name)
        async with (
            self.lock_registry.get(name=general_lock_name, namespace=self.lock_namespace),
            self.lock_registry.get(name=incremental_lock_name, namespace=self.lock_namespace),
        ):
            log.info(f"Acquired lock to run branch diff update for {base_branch.name} - {diff_branch.name}")
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
            )
            if not enriched_diffs:
                return None
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff)
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff)
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.info(f"Branch diff update complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    async def create_or_update_arbitrary_timeframe_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        name: str | None = None,
    ) -> EnrichedDiffRoot:
        tracking_id = None
        if name:
            tracking_id = NameTrackingId(name=name)
        general_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=False
        )
        async with self.lock_registry.get(name=general_lock_name, namespace=self.lock_namespace):
            log.info(f"Acquired lock to run arbitrary diff update for {base_branch.name} - {diff_branch.name}")
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
            )
            if not enriched_diffs:
                return await self.diff_repo.get_one(diff_branch_name=diff_branch.name, tracking_id=tracking_id)

            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff)
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff)
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.info(f"Arbitrary diff update complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    async def recalculate(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        diff_id: str,
    ) -> EnrichedDiffRoot:
        general_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=False
        )
        async with self.lock_registry.get(name=general_lock_name, namespace=self.lock_namespace):
            log.info(f"Acquired lock to recalculate diff for {base_branch.name} - {diff_branch.name}")
            current_branch_diff = await self.diff_repo.get_one(diff_branch_name=diff_branch.name, diff_id=diff_id)
            current_base_diff = await self.diff_repo.get_one(
                diff_branch_name=base_branch.name, diff_id=current_branch_diff.partner_uuid
            )
            if current_branch_diff.tracking_id and isinstance(current_branch_diff.tracking_id, BranchTrackingId):
                to_time = Timestamp()
            else:
                to_time = current_branch_diff.to_time
            await self.diff_repo.delete_diff_roots(diff_root_uuids=[current_branch_diff.uuid, current_base_diff.uuid])
            from_time = current_branch_diff.from_time
            branched_from_time = Timestamp(diff_branch.get_branched_from())
            from_time = max(from_time, branched_from_time)
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=branched_from_time,
                to_time=to_time,
                tracking_id=current_branch_diff.tracking_id,
                force_branch_refresh=True,
            )
            if not enriched_diffs:
                return await self.diff_repo.get_one(
                    diff_branch_name=diff_branch.name, tracking_id=current_branch_diff.tracking_id
                )

            if current_branch_diff:
                await self.conflict_transferer.transfer(
                    earlier=current_branch_diff, later=enriched_diffs.diff_branch_diff
                )

            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff)
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff)
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.info(f"Diff recalculation complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    def _get_ordered_diff_pairs(
        self, diff_pairs: Iterable[EnrichedDiffsEmpty], allow_overlap: bool = False
    ) -> list[EnrichedDiffsEmpty]:
        ordered_diffs = sorted(diff_pairs, key=lambda d: d.diff_branch_diff.from_time)
        if allow_overlap:
            return ordered_diffs
        ordered_diffs_no_overlaps: list[EnrichedDiffsEmpty] = []
        for candidate_diff_pair in ordered_diffs:
            if not ordered_diffs_no_overlaps:
                ordered_diffs_no_overlaps.append(candidate_diff_pair)
                continue
            # no time overlap
            previous_diff = ordered_diffs_no_overlaps[-1].diff_branch_diff
            candidate_diff = candidate_diff_pair.diff_branch_diff
            if previous_diff.to_time <= candidate_diff.from_time:
                ordered_diffs_no_overlaps.append(candidate_diff_pair)
                continue
            previous_interval = previous_diff.time_range
            candidate_interval = candidate_diff.time_range
            # keep the diff that covers the larger time frame
            if candidate_interval > previous_interval:
                ordered_diffs_no_overlaps[-1] = candidate_diff_pair
        return ordered_diffs_no_overlaps

    def _build_empty_enriched_diffs(self, diff_request: EnrichedDiffRequest) -> EnrichedDiffs:
        base_uuid = str(uuid4())
        branch_uuid = str(uuid4())
        return EnrichedDiffs(
            base_branch_name=diff_request.base_branch.name,
            diff_branch_name=diff_request.diff_branch.name,
            base_branch_diff=EnrichedDiffRoot(
                base_branch_name=diff_request.base_branch.name,
                diff_branch_name=diff_request.base_branch.name,
                from_time=diff_request.from_time,
                to_time=diff_request.to_time,
                uuid=base_uuid,
                partner_uuid=branch_uuid,
            ),
            diff_branch_diff=EnrichedDiffRoot(
                base_branch_name=diff_request.base_branch.name,
                diff_branch_name=diff_request.diff_branch.name,
                from_time=diff_request.from_time,
                to_time=diff_request.to_time,
                uuid=branch_uuid,
                partner_uuid=base_uuid,
            ),
        )

    async def _update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        tracking_id: TrackingId | None = None,
        force_branch_refresh: bool = False,
    ) -> EnrichedDiffs | None:
        diff_uuids_to_delete = []
        # start with empty diffs b/c we only care about their metadata for now, hydrate them with data as needed
        empty_diff_pairs = await self.diff_repo.get_empty_diff_pairs(
            base_branch_names=[base_branch.name],
            diff_branch_names=[diff_branch.name],
            from_time=from_time,
            to_time=to_time,
        )
        if tracking_id:
            for diff_pair in empty_diff_pairs:
                if diff_pair.base_branch_diff.tracking_id:
                    diff_uuids_to_delete.append(diff_pair.base_branch_diff.uuid)
                if diff_pair.diff_branch_diff.tracking_id:
                    diff_uuids_to_delete.append(diff_pair.diff_branch_diff.uuid)
        aggregated_enriched_diffs = await self._aggregate_enriched_diffs(
            diff_request=EnrichedDiffRequest(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
            ),
            partial_enriched_diffs=empty_diff_pairs if not force_branch_refresh else [],
        )
        if not aggregated_enriched_diffs:
            return None

        await self.conflicts_enricher.add_conflicts_to_branch_diff(
            base_diff_root=aggregated_enriched_diffs.base_branch_diff,
            branch_diff_root=aggregated_enriched_diffs.diff_branch_diff,
        )
        await self.labels_enricher.enrich(
            enriched_diff_root=aggregated_enriched_diffs.diff_branch_diff, conflicts_only=True
        )

        if tracking_id:
            aggregated_enriched_diffs.base_branch_diff.tracking_id = tracking_id
            aggregated_enriched_diffs.diff_branch_diff.tracking_id = tracking_id
        if diff_uuids_to_delete:
            await self.diff_repo.delete_diff_roots(diff_root_uuids=diff_uuids_to_delete)
        return aggregated_enriched_diffs

    async def _aggregate_enriched_diffs(
        self, diff_request: EnrichedDiffRequest, partial_enriched_diffs: list[EnrichedDiffsEmpty]
    ) -> EnrichedDiffs | None:
        if not partial_enriched_diffs:
            return await self._calculate_enriched_diff(diff_request=diff_request)

        ordered_diffs = self._get_ordered_diff_pairs(diff_pairs=partial_enriched_diffs, allow_overlap=False)
        ordered_diff_reprs = [repr(d) for d in ordered_diffs]
        log.info(f"Ordered diffs for aggregation: {ordered_diff_reprs}")
        incremental_diffs_and_requests: list[EnrichedDiffsEmpty | EnrichedDiffRequest | None] = []
        current_time = diff_request.from_time
        while current_time < diff_request.to_time:
            # the next diff to include has already been calculated
            if ordered_diffs and ordered_diffs[0].diff_branch_diff.from_time == current_time:
                current_diff = ordered_diffs.pop(0)
                incremental_diffs_and_requests.append(current_diff)
                current_time = current_diff.diff_branch_diff.to_time
                continue
            # set the end time to the start of the next calculated diff or the end of the time range
            if ordered_diffs:
                end_time = ordered_diffs[0].diff_branch_diff.from_time
            else:
                end_time = diff_request.to_time
            # if there are no changes on either branch in this time range, then there cannot be a diff
            num_changes_by_branch = await self.diff_repo.get_num_changes_in_time_range_by_branch(
                branch_names=[diff_request.base_branch.name, diff_request.diff_branch.name],
                from_time=current_time,
                to_time=end_time,
            )
            might_have_changes_in_time_range = any(num_changes_by_branch.values())
            if not might_have_changes_in_time_range:
                incremental_diffs_and_requests.append(None)
                current_time = end_time
                continue

            incremental_diffs_and_requests.append(
                EnrichedDiffRequest(
                    base_branch=diff_request.base_branch,
                    diff_branch=diff_request.diff_branch,
                    from_time=current_time,
                    to_time=end_time,
                )
            )
            current_time = end_time

        aggregated_enriched_diffs = await self._concatenate_diffs_and_requests(
            diff_or_request_list=incremental_diffs_and_requests
        )

        if aggregated_enriched_diffs:
            aggregated_enriched_diffs.base_branch_diff.from_time = diff_request.from_time
            aggregated_enriched_diffs.diff_branch_diff.from_time = diff_request.from_time
            aggregated_enriched_diffs.base_branch_diff.to_time = diff_request.to_time
            aggregated_enriched_diffs.diff_branch_diff.to_time = diff_request.to_time
            return aggregated_enriched_diffs
        return self._build_empty_enriched_diffs(diff_request=diff_request)

    async def _concatenate_diffs_and_requests(
        self, diff_or_request_list: list[EnrichedDiffsEmpty | EnrichedDiffRequest | None]
    ) -> EnrichedDiffs | None:
        calculations_required = False
        existing_diff_count = 0
        for diff_or_request in diff_or_request_list:
            # a diff needs to be calculated
            if isinstance(diff_or_request, EnrichedDiffRequest):
                calculations_required = True
                break
            if isinstance(diff_or_request, EnrichedDiffsEmpty):
                existing_diff_count += 1
            # multiple existing diffs need to be added together
            if existing_diff_count > 1:
                calculations_required = True
                break
        if not calculations_required:
            return None

        complete_enriched_diffs: None | EnrichedDiffs = None
        for diff_or_request in diff_or_request_list:
            single_enriched_diffs: EnrichedDiffs | None = None
            if isinstance(diff_or_request, EnrichedDiffsEmpty):
                single_enriched_diffs = await self.diff_repo.hydrate_diff_pair(enriched_diffs=diff_or_request)
            elif isinstance(diff_or_request, EnrichedDiffRequest):
                if complete_enriched_diffs:
                    diff_or_request.node_field_specifiers = self._get_node_field_specifiers(
                        enriched_diff=complete_enriched_diffs.diff_branch_diff
                    )
                single_enriched_diffs = await self._calculate_enriched_diff(diff_request=diff_or_request)
            if not single_enriched_diffs:
                continue
            if complete_enriched_diffs:
                complete_enriched_diffs = await self.diff_combiner.combine(
                    earlier_diffs=complete_enriched_diffs, later_diffs=single_enriched_diffs
                )
            else:
                complete_enriched_diffs = single_enriched_diffs
        return complete_enriched_diffs

    async def _update_core_data_checks(self, enriched_diff: EnrichedDiffRoot) -> list[Node]:
        return await self.data_check_synchronizer.synchronize(enriched_diff=enriched_diff)

    async def _calculate_enriched_diff(self, diff_request: EnrichedDiffRequest) -> EnrichedDiffs:
        calculated_diff_pair = await self.diff_calculator.calculate_diff(
            base_branch=diff_request.base_branch,
            diff_branch=diff_request.diff_branch,
            from_time=diff_request.from_time,
            to_time=diff_request.to_time,
            previous_node_specifiers=diff_request.node_field_specifiers,
        )
        enriched_diff_pair = await self.diff_enricher.enrich(calculated_diffs=calculated_diff_pair)
        return enriched_diff_pair

    def _get_node_field_specifiers(self, enriched_diff: EnrichedDiffRoot) -> set[NodeFieldSpecifier]:
        specifiers: set[NodeFieldSpecifier] = set()
        schema_branch = registry.schema.get_schema_branch(name=enriched_diff.diff_branch_name)
        for node in enriched_diff.nodes:
            specifiers.update(
                NodeFieldSpecifier(node_uuid=node.uuid, field_name=attribute.name) for attribute in node.attributes
            )
            if not node.relationships:
                continue
            node_schema = schema_branch.get_node(name=node.kind, duplicate=False)
            for relationship in node.relationships:
                relationship_schema = node_schema.get_relationship(name=relationship.name)
                specifiers.add(NodeFieldSpecifier(node_uuid=node.uuid, field_name=relationship_schema.get_identifier()))
        return specifiers
