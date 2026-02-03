import pytest

from infrahub.api.validators import CheckBranchStatus
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus


class TestCheckBranchStatus:
    """Tests for the CheckBranchStatus validator class."""

    def test_check_passes_for_open_branch(self) -> None:
        """Test that check passes for OPEN branches."""
        branch = Branch(name="open-branch", status=BranchStatus.OPEN)
        validator = CheckBranchStatus(branch=branch)
        validator.check()

    def test_check_raises_for_merged_branch(self) -> None:
        """Test that check raises ValueError for MERGED branches."""
        branch = Branch(name="merged-branch", status=BranchStatus.MERGED)
        validator = CheckBranchStatus(branch=branch)

        with pytest.raises(ValueError, match=r"merged-branch.*has been merged and is read-only"):
            validator.check()

    def test_check_raises_for_need_rebase_branch(self) -> None:
        """Test that check raises ValueError for NEED_REBASE branches."""
        branch = Branch(name="rebase-branch", status=BranchStatus.NEED_REBASE)
        validator = CheckBranchStatus(branch=branch)

        with pytest.raises(ValueError, match=r"rebase-branch.*must be rebased"):
            validator.check()

    def test_check_passes_for_need_upgrade_rebase_branch(self) -> None:
        """Test that check passes for NEED_UPGRADE_REBASE branches"""
        branch = Branch(name="upgrade-branch", status=BranchStatus.NEED_UPGRADE_REBASE)
        validator = CheckBranchStatus(branch=branch)
        validator.check()

    def test_check_passes_for_deleting_branch(self) -> None:
        """Test that check passes for DELETING branches (deletion in progress)."""
        branch = Branch(name="deleting-branch", status=BranchStatus.DELETING)
        validator = CheckBranchStatus(branch=branch)
        validator.check()
