from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp

from .model.path import DiffRoot


class DiffRepository:
    async def get_calculated_diffs(
        self, base_branch: Branch, diff_branch: Branch, from_time: Timestamp, to_time: Timestamp
    ) -> list[DiffRoot]:
        """Get all diffs for the given branch that touch the given timeframe in chronological order"""
        raise NotImplementedError()

    async def save_diff_root(self, diff_root: DiffRoot) -> None: ...  # pylint: disable=unused-argument
