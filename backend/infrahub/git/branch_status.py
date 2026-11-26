from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.branch import BranchStatus

if TYPE_CHECKING:
    from infrahub_sdk.branch import BranchData

COMMIT_REJECTING_STATUSES = frozenset(
    {
        BranchStatus.NEED_REBASE,
        BranchStatus.MERGING,
        BranchStatus.MERGE_FAILED,
        BranchStatus.MERGED,
        BranchStatus.DELETING,
    }
)
"""The statuses on which the API rejects a repository update, and a branch being deleted."""


def accepts_commit_write(branch: BranchData) -> bool:
    """Whether the graph accepts a commit recorded on this Infrahub branch."""
    return branch.status not in COMMIT_REJECTING_STATUSES
