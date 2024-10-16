from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

from .model.path import (
    BranchTrackingId,
    EnrichedDiffRoot,
    EnrichedDiffs,
    NameTrackingId,
    NodeFieldSpecifier,
    TimeRange,
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
    ) -> EnrichedDiffRoot:
        # we are updating a diff that tracks the full lifetime of a branch
        if not name and not from_time and not to_time:
            return await self.update_branch_diff(base_branch=base_branch, diff_branch=diff_branch)

        if from_time:
            from_timestamp = Timestamp(from_time)
        else:
            from_timestamp = Timestamp(diff_branch.get_branched_from())
        if to_time:
            to_timestamp = Timestamp(to_time)
        else:
            to_timestamp = Timestamp()
        return await self.create_or_update_arbitrary_timeframe_diff(
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

    async def update_branch_diff(self, base_branch: Branch, diff_branch: Branch) -> EnrichedDiffRoot:
        log.debug(f"Received request to update branch diff for {base_branch.name} - {diff_branch.name}")
        incremental_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=True
        )
        existing_incremental_lock = self.lock_registry.get_existing(
            name=incremental_lock_name, namespace=self.lock_namespace
        )
        if existing_incremental_lock and await existing_incremental_lock.locked():
            log.debug(f"Branch diff update for {base_branch.name} - {diff_branch.name} already in progress")
            async with self.lock_registry.get(name=incremental_lock_name, namespace=self.lock_namespace):
                log.debug(f"Existing branch diff update for {base_branch.name} - {diff_branch.name} complete")
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
            log.debug(f"Acquired lock to run branch diff update for {base_branch.name} - {diff_branch.name}")
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
            )
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff)
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff)
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.debug(f"Branch diff update complete for {base_branch.name} - {diff_branch.name}")
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
            log.debug(f"Acquired lock to run arbitrary diff update for {base_branch.name} - {diff_branch.name}")
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
            )
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff)
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff)
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.debug(f"Arbitrary diff update complete for {base_branch.name} - {diff_branch.name}")
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
            log.debug(f"Acquired lock to recalculate diff for {base_branch.name} - {diff_branch.name}")
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

            if current_branch_diff:
                await self.conflict_transferer.transfer(
                    earlier=current_branch_diff, later=enriched_diffs.diff_branch_diff
                )

            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff)
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff)
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.debug(f"Diff recalculation complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    async def _update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        tracking_id: TrackingId | None = None,
        force_branch_refresh: bool = False,
    ) -> EnrichedDiffs:
        diff_uuids_to_delete = []
        retrieved_enriched_diffs = await self.diff_repo.get_pairs(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            from_time=from_time,
            to_time=to_time,
        )
        for enriched_diffs in retrieved_enriched_diffs:
            if tracking_id:
                if enriched_diffs.base_branch_diff.tracking_id:
                    diff_uuids_to_delete.append(enriched_diffs.base_branch_diff.uuid)
                if enriched_diffs.diff_branch_diff.tracking_id:
                    diff_uuids_to_delete.append(enriched_diffs.diff_branch_diff.uuid)
        aggregated_enriched_diffs = await self._get_aggregated_enriched_diffs(
            diff_request=EnrichedDiffRequest(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
            ),
            partial_enriched_diffs=retrieved_enriched_diffs if not force_branch_refresh else [],
        )

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

    async def _get_aggregated_enriched_diffs(
        self, diff_request: EnrichedDiffRequest, partial_enriched_diffs: list[EnrichedDiffs]
    ) -> EnrichedDiffs:
        if not partial_enriched_diffs:
            return await self._get_enriched_diff(diff_request=diff_request)

        remaining_diffs = sorted(partial_enriched_diffs, key=lambda d: d.diff_branch_diff.from_time)
        current_time = diff_request.from_time
        previous_diffs: EnrichedDiffs | None = None
        while current_time < diff_request.to_time:
            if remaining_diffs and remaining_diffs[0].diff_branch_diff.from_time == current_time:
                current_diffs = remaining_diffs.pop(0)
            else:
                if remaining_diffs:
                    end_time = remaining_diffs[0].diff_branch_diff.from_time
                else:
                    end_time = diff_request.to_time
                if previous_diffs is None:
                    node_field_specifiers = set()
                else:
                    node_field_specifiers = self._get_node_field_specifiers(
                        enriched_diff=previous_diffs.diff_branch_diff
                    )
                inner_diff_request = EnrichedDiffRequest(
                    base_branch=diff_request.base_branch,
                    diff_branch=diff_request.diff_branch,
                    from_time=current_time,
                    to_time=end_time,
                    node_field_specifiers=node_field_specifiers,
                )
                current_diffs = await self._get_enriched_diff(diff_request=inner_diff_request)

            if previous_diffs:
                current_diffs = await self.diff_combiner.combine(
                    earlier_diffs=previous_diffs, later_diffs=current_diffs
                )

            previous_diffs = current_diffs
            current_time = current_diffs.diff_branch_diff.to_time

        return current_diffs

    async def _update_core_data_checks(self, enriched_diff: EnrichedDiffRoot) -> list[Node]:
        return await self.data_check_synchronizer.synchronize(enriched_diff=enriched_diff)

    async def _get_enriched_diff(self, diff_request: EnrichedDiffRequest) -> EnrichedDiffs:
        calculated_diff_pair = await self.diff_calculator.calculate_diff(
            base_branch=diff_request.base_branch,
            diff_branch=diff_request.diff_branch,
            from_time=diff_request.from_time,
            to_time=diff_request.to_time,
            previous_node_specifiers=diff_request.node_field_specifiers,
        )
        enriched_diff_pair = await self.diff_enricher.enrich(calculated_diffs=calculated_diff_pair)
        return enriched_diff_pair

    def _get_missing_time_ranges(
        self, time_ranges: list[TimeRange], from_time: Timestamp, to_time: Timestamp
    ) -> list[TimeRange]:
        if not time_ranges:
            return [TimeRange(from_time=from_time, to_time=to_time)]
        sorted_time_ranges = sorted(time_ranges, key=lambda tr: tr.from_time)
        missing_time_ranges = []
        if sorted_time_ranges[0].from_time > from_time:
            missing_time_ranges.append(TimeRange(from_time=from_time, to_time=sorted_time_ranges[0].from_time))
        index = 0
        while index < len(sorted_time_ranges) - 1:
            this_diff = sorted_time_ranges[index]
            next_diff = sorted_time_ranges[index + 1]
            if this_diff.to_time < next_diff.from_time:
                missing_time_ranges.append(TimeRange(from_time=this_diff.to_time, to_time=next_diff.from_time))
            index += 1
        if sorted_time_ranges[-1].to_time < to_time:
            missing_time_ranges.append(TimeRange(from_time=sorted_time_ranges[-1].to_time, to_time=to_time))
        return missing_time_ranges

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
