from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp

from .model.path import BranchTrackingId, EnrichedDiffRoot, NameTrackingId, TimeRange, TrackingId

if TYPE_CHECKING:
    from infrahub.core.branch import Branch

    from .calculator import DiffCalculator
    from .combiner import DiffCombiner
    from .conflicts_enricher import ConflictsEnricher
    from .enricher.aggregated import AggregatedDiffEnricher
    from .enricher.summary_counts import DiffSummaryCountsEnricher
    from .repository.repository import DiffRepository


class DiffCoordinator:
    def __init__(
        self,
        diff_repo: DiffRepository,
        diff_calculator: DiffCalculator,
        diff_enricher: AggregatedDiffEnricher,
        diff_combiner: DiffCombiner,
        conflicts_enricher: ConflictsEnricher,
        summary_counts_enricher: DiffSummaryCountsEnricher,
    ) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_enricher = diff_enricher
        self.diff_combiner = diff_combiner
        self.conflicts_enricher = conflicts_enricher
        self.summary_counts_enricher = summary_counts_enricher

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
        retrieved_enriched_branch_diffs = await self.diff_repo.get(
            base_branch_name=base_branch.name,
            diff_branch_names=[diff_branch.name],
            from_time=from_time,
            to_time=to_time,
        )
        retrieved_enriched_base_diffs = await self.diff_repo.get(
            base_branch_name=base_branch.name,
            diff_branch_names=[base_branch.name],
            from_time=from_time,
            to_time=to_time,
        )
        covered_time_ranges = [
            TimeRange(from_time=enriched_diff.from_time, to_time=enriched_diff.to_time)
            for enriched_diff in retrieved_enriched_branch_diffs
        ]
        missing_time_ranges = self._get_missing_time_ranges(
            time_ranges=covered_time_ranges, from_time=from_time, to_time=to_time
        )
        all_enriched_branch_diffs = list(retrieved_enriched_branch_diffs)
        all_enriched_base_diffs = list(retrieved_enriched_base_diffs)
        for missing_time_range in missing_time_ranges:
            calculated_diff_pair = await self.diff_calculator.calculate_diff(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=missing_time_range.from_time,
                to_time=missing_time_range.to_time,
            )
            enriched_diff_pair = await self.diff_enricher.enrich(calculated_diffs=calculated_diff_pair)
            all_enriched_branch_diffs.append(enriched_diff_pair.diff_branch_diff)
            all_enriched_base_diffs.append(enriched_diff_pair.base_branch_diff)

        all_enriched_branch_diffs.sort(key=lambda e_diff: e_diff.from_time)
        combined_branch_diff = all_enriched_branch_diffs[0]
        for next_diff in all_enriched_branch_diffs[1:]:
            combined_branch_diff = await self.diff_combiner.combine(
                earlier_diff=combined_branch_diff, later_diff=next_diff
            )
        all_enriched_base_diffs.sort(key=lambda e_diff: e_diff.from_time)
        combined_base_diff = all_enriched_base_diffs[0]
        for next_diff in all_enriched_base_diffs[1:]:
            combined_base_diff = await self.diff_combiner.combine(earlier_diff=combined_base_diff, later_diff=next_diff)

        await self.conflicts_enricher.add_conflicts_to_branch_diff(
            base_diff_root=combined_base_diff, branch_diff_root=combined_branch_diff
        )
        await self.summary_counts_enricher.enrich(enriched_diff_root=combined_base_diff)
        await self.summary_counts_enricher.enrich(enriched_diff_root=combined_branch_diff)

        if tracking_id:
            uuids_to_delete = [
                diff.uuid
                for diff in retrieved_enriched_base_diffs + retrieved_enriched_branch_diffs
                if diff.tracking_id == tracking_id
            ]
            await self.diff_repo.delete_diff_roots(diff_root_uuids=uuids_to_delete)
            combined_base_diff.tracking_id = tracking_id
            combined_branch_diff.tracking_id = tracking_id

        await self.diff_repo.save(enriched_diff=combined_base_diff)
        await self.diff_repo.save(enriched_diff=combined_branch_diff)
        return combined_branch_diff

    def _get_missing_time_ranges(
        self, time_ranges: list[TimeRange], from_time: Timestamp, to_time: Timestamp
    ) -> list[TimeRange]:
        if not time_ranges:
            return [TimeRange(from_time=from_time, to_time=to_time)]
        missing_time_ranges = []
        if time_ranges[0].from_time > from_time:
            missing_time_ranges.append(TimeRange(from_time=from_time, to_time=time_ranges[0].from_time))
        index = 0
        while index < len(time_ranges) - 1:
            this_diff = time_ranges[index]
            next_diff = time_ranges[index + 1]
            if this_diff.to_time != next_diff.from_time:
                missing_time_ranges.append(TimeRange(from_time=this_diff.to_time, to_time=next_diff.from_time))
            index += 1
        if time_ranges[-1].to_time < to_time:
            missing_time_ranges.append(TimeRange(from_time=time_ranges[-1].to_time, to_time=to_time))
        return missing_time_ranges
