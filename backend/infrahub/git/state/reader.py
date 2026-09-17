from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import RepositoryGitCondition, RepositoryGitUnavailableReason

from .models import BranchDriftResult, CommitLogResult

if TYPE_CHECKING:
    from .models import BranchHeadsRequest, CommitLogRequest

NOT_IMPLEMENTED_MESSAGE = "Reading git state from a worker is not available in this version."


class RepositoryGitStateReader(Protocol):
    """Answer a repository's git state for one Infrahub branch, or for every branch at once.

    An implementation never clones, fetches or takes a repository lock.
    """

    async def commits(self, request: CommitLogRequest) -> CommitLogResult: ...

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult: ...


class UnavailableRepositoryGitStateReader:
    """Answer that no git-derived state can be produced."""

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:  # noqa: ARG002
        return CommitLogResult(
            condition=RepositoryGitCondition.UNAVAILABLE,
            unavailable_reason=RepositoryGitUnavailableReason.NOT_IMPLEMENTED,
            error_message=NOT_IMPLEMENTED_MESSAGE,
        )

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult:  # noqa: ARG002
        return BranchDriftResult(
            unavailable_reason=RepositoryGitUnavailableReason.NOT_IMPLEMENTED,
            error_message=NOT_IMPLEMENTED_MESSAGE,
        )
