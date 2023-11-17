from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.core.branch import Branch, Diff
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import DiffFromRequiredOnDefaultBranchError, DiffRangeValidationError


class TestDiffInit:
    def setup_method(self):
        self.db = MagicMock()
        self.origin_branch = Branch(name="origin")
        self.created_at_str = "2023-11-01"
        self.created_at_timestamp = Timestamp(self.created_at_str)
        self.branch = AsyncMock(spec=Branch)
        self.branch.name = "branch"
        self.branch.is_default = False
        self.branch.created_at = self.created_at_str
        self.branch.get_origin_branch.return_value = self.origin_branch

    async def __call_system_under_test(self, branch, **kwargs):
        return await Diff.init(self.db, branch, **kwargs)

    async def test_diff_from_required_for_default_branch(self):
        self.branch.is_default = True

        with pytest.raises(DiffFromRequiredOnDefaultBranchError):
            await self.__call_system_under_test(self.branch)

    async def test_diff_to_cannot_precede_diff_from(self):
        bad_diff_to = "2023-10-31"

        with pytest.raises(DiffRangeValidationError):
            await self.__call_system_under_test(self.branch, diff_to=bad_diff_to)

    async def test_diff_from_default_is_set(self):
        diff_to_str = "2023-11-15"

        diff = await self.__call_system_under_test(self.branch, diff_to=diff_to_str)

        self.branch.get_origin_branch.assert_awaited_once_with(db=self.db)
        assert diff.branch == self.branch
        assert diff.origin_branch == self.origin_branch
        assert diff.diff_from == self.created_at_timestamp
        assert diff.diff_to == Timestamp(diff_to_str)
