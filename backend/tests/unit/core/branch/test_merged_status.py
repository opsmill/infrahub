import pytest

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchAlreadyMergedError


def test_check_merged_status_raises_for_merged_branch() -> None:
    branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

    with pytest.raises(
        BranchAlreadyMergedError, match=r"merged-branch.*has been merged and is read-only. No modifications are allowed"
    ):
        BranchStatusChecker().check_merge_status(branch=branch)


@pytest.mark.parametrize(
    "status",
    [
        BranchStatus.OPEN,
        BranchStatus.NEED_REBASE,
        BranchStatus.DELETING,
        BranchStatus.NEED_UPGRADE_REBASE,
    ],
)
def test_check_merged_status_passes_for_non_merged_branch(status: BranchStatus) -> None:
    branch = Branch(name="test-branch", status=status)
    BranchStatusChecker().check_merge_status(branch=branch)
