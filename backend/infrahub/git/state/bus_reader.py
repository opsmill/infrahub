from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryGitUnavailableReason
from infrahub.message_bus.messages.git_commit_log_get import GitCommitLogGetResponse

from .commit_log_wire import request_to_message, response_data_to_result
from .models import BranchDriftResult
from .reader import NOT_IMPLEMENTED_MESSAGE

if TYPE_CHECKING:
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

    from .models import BranchHeadsRequest, CommitLogRequest, CommitLogResult


class BusRepositoryGitStateReader:
    """Answer from whichever worker takes the request off the message bus."""

    def __init__(self, message_bus: InfrahubMessageBus, timeout: float) -> None:
        self._message_bus = message_bus
        self._timeout = timeout

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:
        """Return the commit log a worker read from its local clone.

        Raises:
            WorkerTimeoutError: When no worker answered within the timeout.
            RPCError: When the worker failed to produce an answer, or produced an unusable one.

        """
        response = await self._message_bus.rpc(
            message=request_to_message(request=request),
            response_class=GitCommitLogGetResponse,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response_data_to_result(data=response.data)

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult:  # noqa: ARG002
        """Answer that per-branch heads are unavailable."""
        return BranchDriftResult(
            unavailable_reason=RepositoryGitUnavailableReason.NOT_IMPLEMENTED,
            error_message=NOT_IMPLEMENTED_MESSAGE,
        )
