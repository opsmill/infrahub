import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.merged_status import check_merged_status


def test_check_merged_status_raises_for_merged_branch() -> None:
    branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

    with pytest.raises(ValueError, match=r"merged-branch.*has been merged and is read-only"):
        check_merged_status(branch)


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
    check_merged_status(branch)
