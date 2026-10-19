from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryGitCondition
from infrahub.git.state.models import CommitLogResult

if TYPE_CHECKING:
    from infrahub.git.state.models import CommitLogRequest


class RecordingRepositoryGitStateReader:
    """Record every request in order and replay queued results.

    The recorded requests are what make "no request was made" and "the request carried this branch
    and this flag" assertable as full dataclass equality.
    """

    def __init__(self, commit_results: list[CommitLogResult] | None = None) -> None:
        self.commit_requests: list[CommitLogRequest] = []
        self.commit_results = list(commit_results or [])

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:
        self.commit_requests.append(request)
        if self.commit_results:
            return self.commit_results.pop(0)
        return CommitLogResult(condition=RepositoryGitCondition.NOT_TRACKED)


class FailingRepositoryGitStateReader:
    """Raise on every read, to prove what a consumer claims to survive."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:
        raise self._error
