from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryGitCondition
from infrahub.git.state.models import BranchDriftResult, CommitLogResult

if TYPE_CHECKING:
    from infrahub.git.state.models import BranchHeadsRequest, CommitLogRequest


class RecordingRepositoryGitStateReader:
    """Record every request in order and replay queued results.

    The recorded requests are what make "no request was made" and "the request carried this branch
    and this flag" assertable as full dataclass equality.
    """

    def __init__(
        self,
        commit_results: list[CommitLogResult] | None = None,
        branch_heads_results: list[BranchDriftResult] | None = None,
    ) -> None:
        self.commit_requests: list[CommitLogRequest] = []
        self.branch_heads_requests: list[BranchHeadsRequest] = []
        self.commit_results = list(commit_results or [])
        self.branch_heads_results = list(branch_heads_results or [])

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:
        self.commit_requests.append(request)
        if self.commit_results:
            return self.commit_results.pop(0)
        return CommitLogResult(condition=RepositoryGitCondition.NOT_TRACKED)

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult:
        self.branch_heads_requests.append(request)
        if self.branch_heads_results:
            return self.branch_heads_results.pop(0)
        return BranchDriftResult()


class FailingRepositoryGitStateReader:
    """Raise on every read, to prove what a consumer claims to survive."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:
        raise self._error

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult:
        raise self._error
