from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp

from .model.path import BranchTrackingId, EnrichedDiffRoot, NameTrackingId, TimeRange, TrackingId

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node

    from .calculator import DiffCalculator
    from .combiner import DiffCombiner
    from .conflicts_enricher import ConflictsEnricher
    from .data_check_synchronizer import DiffDataCheckSynchronizer
    from .enricher.aggregated import AggregatedDiffEnricher
    from .enricher.summary_counts import DiffSummaryCountsEnricher
    from .repository.repository import DiffRepository


@dataclass
class EnrichedDiffRequest:
    base_branch: Branch
    diff_branch: Branch
    from_time: Timestamp
    to_time: Timestamp

    def __hash__(self) -> int:
        hash_keys = [self.base_branch.name, self.diff_branch.name, self.from_time.to_string(), self.to_time.to_string()]
        return hash("-".join(hash_keys))


class DiffCoordinator:
    def __init__(
        self,
        diff_repo: DiffRepository,
        diff_calculator: DiffCalculator,
        diff_enricher: AggregatedDiffEnricher,
        diff_combiner: DiffCombiner,
        conflicts_enricher: ConflictsEnricher,
        summary_counts_enricher: DiffSummaryCountsEnricher,
        data_check_synchronizer: DiffDataCheckSynchronizer,
    ) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_enricher = diff_enricher
        self.diff_combiner = diff_combiner
        self.conflicts_enricher = conflicts_enricher
        self.summary_counts_enricher = summary_counts_enricher
        self.data_check_synchronizer = data_check_synchronizer
        self._enriched_diff_cache: dict[EnrichedDiffRequest, EnrichedDiffRoot] = {}

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
            from_timestamp = Timestamp(diff_branch.get_created_at())
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

    async def update_branch_diff(self, base_branch: Branch, diff_branch: Branch) -> EnrichedDiffRoot:
        from_time = Timestamp(diff_branch.get_created_at())
        to_time = Timestamp()
        tracking_id = BranchTrackingId(name=diff_branch.name)
        return await self._update_diffs(
            base_branch=base_branch,
            diff_branch=diff_branch,
            from_time=from_time,
            to_time=to_time,
            tracking_id=tracking_id,
        )

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
        return await self._update_diffs(
            base_branch=base_branch,
            diff_branch=diff_branch,
            from_time=from_time,
            to_time=to_time,
            tracking_id=tracking_id,
        )

    async def _update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        tracking_id: TrackingId | None = None,
    ) -> EnrichedDiffRoot:
        requested_diff_branches = {base_branch.name: base_branch, diff_branch.name: diff_branch}
        aggregated_diffs_by_branch_name: dict[str, EnrichedDiffRoot] = {}
        diff_uuids_to_delete = []
        for branch in requested_diff_branches.values():
            retrieved_enriched_diffs = await self.diff_repo.get(
                base_branch_name=base_branch.name,
                diff_branch_names=[branch.name],
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
            )
            if tracking_id:
                diff_uuids_to_delete += [
                    diff.uuid for diff in retrieved_enriched_diffs if diff.tracking_id == tracking_id
                ]
            covered_time_ranges = [
                TimeRange(from_time=enriched_diff.from_time, to_time=enriched_diff.to_time)
                for enriched_diff in retrieved_enriched_diffs
            ]
            missing_time_ranges = self._get_missing_time_ranges(
                time_ranges=covered_time_ranges, from_time=from_time, to_time=to_time
            )
            all_enriched_diffs = list(retrieved_enriched_diffs)
            for missing_time_range in missing_time_ranges:
                diff_request = EnrichedDiffRequest(
                    base_branch=base_branch,
                    diff_branch=branch,
                    from_time=missing_time_range.from_time,
                    to_time=missing_time_range.to_time,
                )
                enriched_diff = await self._get_enriched_diff(diff_request=diff_request)
                all_enriched_diffs.append(enriched_diff)
            all_enriched_diffs.sort(key=lambda e_diff: e_diff.from_time)
            combined_diff = all_enriched_diffs[0]
            for next_diff in all_enriched_diffs[1:]:
                combined_diff = await self.diff_combiner.combine(earlier_diff=combined_diff, later_diff=next_diff)
            aggregated_diffs_by_branch_name[branch.name] = combined_diff

        if len(aggregated_diffs_by_branch_name) > 1:
            await self.conflicts_enricher.add_conflicts_to_branch_diff(
                base_diff_root=aggregated_diffs_by_branch_name[base_branch.name],
                branch_diff_root=aggregated_diffs_by_branch_name[diff_branch.name],
            )

        if tracking_id:
            for enriched_diff in aggregated_diffs_by_branch_name.values():
                enriched_diff.tracking_id = tracking_id
            if diff_uuids_to_delete:
                await self.diff_repo.delete_diff_roots(diff_root_uuids=diff_uuids_to_delete)

        for enriched_diff in aggregated_diffs_by_branch_name.values():
            await self.summary_counts_enricher.enrich(enriched_diff_root=enriched_diff)
            await self.diff_repo.save(enriched_diff=enriched_diff)
        branch_enriched_diff = aggregated_diffs_by_branch_name[diff_branch.name]
        await self._update_core_data_checks(enriched_diff=enriched_diff)
        return branch_enriched_diff

    async def _update_core_data_checks(self, enriched_diff: EnrichedDiffRoot) -> list[Node]:
        return await self.data_check_synchronizer.synchronize(enriched_diff=enriched_diff)

    async def _get_enriched_diff(self, diff_request: EnrichedDiffRequest) -> EnrichedDiffRoot:
        if diff_request in self._enriched_diff_cache:
            return self._enriched_diff_cache[diff_request]
        calculated_diff_pair = await self.diff_calculator.calculate_diff(
            base_branch=diff_request.base_branch,
            diff_branch=diff_request.diff_branch,
            from_time=diff_request.from_time,
            to_time=diff_request.to_time,
        )
        enriched_diff_pair = await self.diff_enricher.enrich(calculated_diffs=calculated_diff_pair)
        self._enriched_diff_cache[diff_request] = enriched_diff_pair.diff_branch_diff
        if diff_request.base_branch.name != diff_request.diff_branch.name:
            base_diff_request = replace(diff_request, diff_branch=diff_request.base_branch)
            self._enriched_diff_cache[base_diff_request] = enriched_diff_pair.base_branch_diff
        return enriched_diff_pair.diff_branch_diff

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
