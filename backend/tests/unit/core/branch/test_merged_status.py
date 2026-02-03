from unittest.mock import MagicMock

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.merged_status import check_merged_status


def test_check_merged_status_raises_for_merged_branch() -> None:
    mock_branch = MagicMock()
    mock_branch.status = BranchStatus.MERGED
    mock_branch.name = "merged-branch"

    with pytest.raises(ValueError, match=r"merged-branch.*has been merged and is read-only"):
        check_merged_status(mock_branch)


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
    mock_branch = MagicMock()
    mock_branch.status = status
    mock_branch.name = "test-branch"

    check_merged_status(mock_branch)
