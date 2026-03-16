import pytest

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchAlreadyMergedError, BranchNeedsRebaseError


class TestBranchStatusChecker:
    """Tests for the BranchStatusChecker().check validator class."""

    def test_check_passes_for_open_branch(self) -> None:
        """Test that check passes for OPEN branches."""
        branch = Branch(name="open-branch", status=BranchStatus.OPEN)
        BranchStatusChecker().check(branch=branch)

    def test_check_raises_for_merged_branch(self) -> None:
        """Test that check raises BranchAlreadyMergedError for MERGED branches."""
        branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

        with pytest.raises(
            BranchAlreadyMergedError,
            match=r"merged-branch.*has been merged and is read-only. No modifications are allowed",
        ):
            BranchStatusChecker().check(branch=branch)

    def test_check_raises_for_need_rebase_branch(self) -> None:
        """Test that check raises BranchNeedsRebaseError for NEED_REBASE branches."""
        branch = Branch(name="rebase-branch", status=BranchStatus.NEED_REBASE)

        with pytest.raises(BranchNeedsRebaseError, match=r"rebase-branch.*must be rebased"):
            BranchStatusChecker().check(branch=branch)

    def test_check_passes_for_need_upgrade_rebase_branch(self) -> None:
        """Test that check passes for NEED_UPGRADE_REBASE branches"""
        branch = Branch(name="upgrade-branch", status=BranchStatus.NEED_UPGRADE_REBASE)
        BranchStatusChecker().check(branch=branch)

    def test_check_passes_for_deleting_branch(self) -> None:
        """Test that check passes for DELETING branches (deletion in progress)."""
        branch = Branch(name="deleting-branch", status=BranchStatus.DELETING)
        BranchStatusChecker().check(branch=branch)
