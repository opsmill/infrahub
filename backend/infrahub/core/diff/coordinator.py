from functools import reduce

from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp

from .calculator import DiffCalculator
from .combiner import DiffCombiner
from .model.path import DiffRoot
from .repository import DiffRepository


class DiffCoordinator:
    def __init__(self, diff_repo: DiffRepository, diff_calculator: DiffCalculator, diff_combiner: DiffCombiner) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_combiner = diff_combiner

    async def get_diff(
        self, base_branch: Branch, diff_branch: Branch, from_time: Timestamp, to_time: Timestamp
    ) -> DiffRoot:
        calculated_timeframe_diffs = await self.diff_repo.get_calculated_diffs(
            base_branch=base_branch, diff_branch=diff_branch, from_time=from_time, to_time=to_time
        )
        missing_time_ranges = self._get_missing_time_ranges(
            calculated_diffs=calculated_timeframe_diffs, from_time=from_time, to_time=to_time
        )
        missing_time_range_diffs = []
        for missing_from_time, missing_to_time in missing_time_ranges:
            calculated_diffs = await self.diff_calculator.calculate_diff(
                base_branch=base_branch, diff_branch=diff_branch, from_time=missing_from_time, to_time=missing_to_time
            )
            await self.diff_repo.save_diff_root(diff_root=calculated_diffs.base_branch_diff)
            await self.diff_repo.save_diff_root(diff_root=calculated_diffs.diff_branch_diff)
            missing_time_range_diffs.append(calculated_diffs.diff_branch_diff)
        full_time_range_diffs = calculated_timeframe_diffs + missing_time_range_diffs
        full_time_range_diffs.sort(key=lambda dr: dr.from_time)
        first_diff = full_time_range_diffs.pop(0)
        combined_diff = reduce(
            lambda first, second: self.diff_combiner.combine(earlier_diff=first, later_diff=second),
            full_time_range_diffs,
            first_diff,
        )
        return combined_diff

    def _get_missing_time_ranges(  # pylint: disable=unused-argument
        self, calculated_diffs: list[DiffRoot], from_time: Timestamp, to_time: Timestamp
    ) -> list[tuple[Timestamp, Timestamp]]:
        return [(Timestamp(), Timestamp())]
