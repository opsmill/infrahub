from copy import deepcopy

from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp

from .calculator import DiffCalculator
from .combiner import DiffCombiner
from .enricher.aggregated import AggregatedDiffEnricher
from .model.path import EnrichedDiffRoot, TimeRange
from .repository.repository import DiffRepository


class DiffCoordinator:
    def __init__(
        self,
        diff_repo: DiffRepository,
        diff_calculator: DiffCalculator,
        diff_enricher: AggregatedDiffEnricher,
        diff_combiner: DiffCombiner,
    ) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_enricher = diff_enricher
        self.diff_combiner = diff_combiner

    async def get_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        root_node_uuids: list[str] | None = None,
        max_depth: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> EnrichedDiffRoot:
        covered_time_ranges = await self.diff_repo.get_time_ranges(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            from_time=from_time,
            to_time=to_time,
        )
        missing_time_ranges = self._get_missing_time_ranges(
            time_ranges=covered_time_ranges, from_time=from_time, to_time=to_time
        )
        for missing_time_range in missing_time_ranges:
            calculated_diffs = await self.diff_calculator.calculate_diff(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=missing_time_range.from_time,
                to_time=missing_time_range.to_time,
            )
            enriched_diff = await self.diff_enricher.enrich(calculated_diffs=calculated_diffs)
            await self.diff_repo.save(enriched_diff=enriched_diff)
        calculated_timeframe_diffs = await self.diff_repo.get(
            base_branch_name=base_branch.name,
            diff_branch_names=[diff_branch.name],
            from_time=from_time,
            to_time=to_time,
            root_node_uuids=root_node_uuids,
            max_depth=max_depth,
            limit=limit,
            offset=offset,
        )
        calculated_timeframe_diffs.sort(key=lambda dr: dr.from_time)
        combined_diff = deepcopy(calculated_timeframe_diffs[0])
        for calculated_diff in calculated_timeframe_diffs[1:]:
            combined_diff = await self.diff_combiner.combine(earlier_diff=combined_diff, later_diff=calculated_diff)
        return combined_diff

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
