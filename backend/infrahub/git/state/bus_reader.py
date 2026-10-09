from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.message_bus.messages.git_branch_heads_get import GitBranchHeadsGetResponse
from infrahub.message_bus.messages.git_commit_log_get import GitCommitLogGetResponse

from . import branch_heads_wire, commit_log_wire

if TYPE_CHECKING:
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

    from .models import BranchDriftResult, BranchHeadsRequest, CommitLogRequest, CommitLogResult


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
            message=commit_log_wire.request_to_message(request=request),
            response_class=GitCommitLogGetResponse,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return commit_log_wire.response_data_to_result(data=response.data)

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult:
        """Return the remote head and condition of every requested branch, read by one worker in one request.

        Raises:
            WorkerTimeoutError: When no worker answered within the timeout.
            RPCError: When the worker failed to produce an answer, or produced an unusable one.

        """
        response = await self._message_bus.rpc(
            message=branch_heads_wire.request_to_message(request=request),
            response_class=GitBranchHeadsGetResponse,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return branch_heads_wire.response_data_to_result(data=response.data)
