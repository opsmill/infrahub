from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar

import pytest
import ujson

from infrahub.core.constants import (
    InfrahubKind,
    RepositoryCommitState,
    RepositoryGitCondition,
    RepositoryGitUnavailableReason,
)
from infrahub.exceptions import RPCError
from infrahub.git.state.bus_reader import BusRepositoryGitStateReader
from infrahub.git.state.models import CommitEntry, CommitLogRequest, CommitLogResult
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, RPCErrorResponse
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.messages.git_commit_log_get import (
    GitCommitLogEntry,
    GitCommitLogGet,
    GitCommitLogGetResponse,
    GitCommitLogGetResponseData,
)
from infrahub.services.adapters.message_bus import InfrahubMessageBus

if TYPE_CHECKING:
    from infrahub.message_bus.types import MessageTTL

ResponseClass = TypeVar("ResponseClass")

HEAD = "3333333333333333333333333333333333333333"
IMPORTED = "1111111111111111111111111111111111111111"
AUTHORED_AT = datetime(2026, 9, 8, 10, 30, tzinfo=UTC)
COMMITTED_AT = datetime(2026, 9, 8, 10, 45, tzinfo=UTC)
FETCHED_AT = datetime(2026, 9, 8, 11, 0, tzinfo=UTC)
WARM_UP_TASK_ID = "18d39e83-1ef7-d650-5424-000000000000"

REQUEST = CommitLogRequest(
    repository_id="18d39e83-0000-0000-0000-000000000001",
    repository_name="edge",
    repository_kind=InfrahubKind.REPOSITORY,
    location="https://git.example.com/edge.git",
    infrahub_branch_name="main",
    git_ref="trunk",
    imported_commit=IMPORTED,
    limit=25,
    offset=50,
    include_pending_count=True,
)


@dataclass(frozen=True)
class RPCCall:
    routing_key: str
    message: InfrahubMessage
    timeout: float | None


class RecordingRPCBus(InfrahubMessageBus):
    """Records every request in order and answers each with the next queued reply, sent over the wire format."""

    def __init__(self, replies: list[InfrahubResponse]) -> None:
        self.calls: list[RPCCall] = []
        self._replies = list(replies)

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        raise ValueError("RecordingRPCBus.publish should not be called")

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise ValueError("RecordingRPCBus.reply should not be called")

    async def rpc(
        self,
        message: InfrahubMessage,
        response_class: type[ResponseClass],
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> ResponseClass:
        self.calls.append(RPCCall(routing_key=ROUTING_KEY_MAP[type(message)], message=message, timeout=timeout))
        return response_class(**ujson.loads(self._replies.pop(0).body))


async def test_sends_the_request_with_the_configured_timeout_and_maps_the_reply() -> None:
    bus = RecordingRPCBus(
        replies=[
            GitCommitLogGetResponse(
                data=GitCommitLogGetResponseData(
                    condition=RepositoryGitCondition.BEHIND,
                    remote_head=HEAD,
                    imported_commit=IMPORTED,
                    pending_count=4,
                    fetched_at=FETCHED_AT,
                    commits=[
                        GitCommitLogEntry(
                            hash=HEAD,
                            message="Add a widget\n\nWith a body.",
                            author_name="Ada Lovelace",
                            authored_at=AUTHORED_AT,
                            committed_at=COMMITTED_AT,
                            state=RepositoryCommitState.HEAD,
                        ),
                        GitCommitLogEntry(
                            hash=IMPORTED,
                            message="Initial import",
                            author_name="Grace Hopper",
                            authored_at=AUTHORED_AT,
                            committed_at=AUTHORED_AT,
                            state=RepositoryCommitState.IMPORTED,
                        ),
                    ],
                )
            )
        ]
    )
    reader = BusRepositoryGitStateReader(message_bus=bus, timeout=12.5)

    result = await reader.commits(request=REQUEST)

    assert bus.calls == [
        RPCCall(
            routing_key="git.commit_log.get",
            message=GitCommitLogGet(
                repository_id="18d39e83-0000-0000-0000-000000000001",
                repository_name="edge",
                repository_kind=InfrahubKind.REPOSITORY,
                location="https://git.example.com/edge.git",
                infrahub_branch_name="main",
                git_ref="trunk",
                imported_commit=IMPORTED,
                limit=25,
                offset=50,
                include_pending_count=True,
            ),
            timeout=12.5,
        )
    ]
    assert result == CommitLogResult(
        condition=RepositoryGitCondition.BEHIND,
        remote_head=HEAD,
        imported_commit=IMPORTED,
        pending_count=4,
        fetched_at=FETCHED_AT,
        commits=(
            CommitEntry(
                hash=HEAD,
                message="Add a widget\n\nWith a body.",
                author_name="Ada Lovelace",
                authored_at=AUTHORED_AT,
                committed_at=COMMITTED_AT,
                state=RepositoryCommitState.HEAD,
            ),
            CommitEntry(
                hash=IMPORTED,
                message="Initial import",
                author_name="Grace Hopper",
                authored_at=AUTHORED_AT,
                committed_at=AUTHORED_AT,
                state=RepositoryCommitState.IMPORTED,
            ),
        ),
    )


async def test_maps_a_not_cloned_reply_with_its_warm_up_and_message() -> None:
    bus = RecordingRPCBus(
        replies=[
            GitCommitLogGetResponse(
                data=GitCommitLogGetResponseData(
                    condition=RepositoryGitCondition.UNAVAILABLE,
                    unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
                    warm_up_task_id=WARM_UP_TASK_ID,
                    error_message="The answering worker holds no local copy of this repository yet.",
                )
            )
        ]
    )
    reader = BusRepositoryGitStateReader(message_bus=bus, timeout=30)

    result = await reader.commits(request=REQUEST)

    assert result == CommitLogResult(
        condition=RepositoryGitCondition.UNAVAILABLE,
        unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
        warm_up_task_id=WARM_UP_TASK_ID,
        error_message="The answering worker holds no local copy of this repository yet.",
    )


async def test_a_failed_worker_reply_raises() -> None:
    bus = RecordingRPCBus(
        replies=[RPCErrorResponse(errors=["The data on disk is not a valid Git repository for edge."])]
    )
    reader = BusRepositoryGitStateReader(message_bus=bus, timeout=30)

    with pytest.raises(RPCError) as raised:
        await reader.commits(request=REQUEST)

    # RPCError carries its message on an attribute and leaves str() empty.
    assert raised.value.message == "The data on disk is not a valid Git repository for edge."


@dataclass(frozen=True)
class UnusableReplyCase:
    name: str
    data: GitCommitLogGetResponseData
    message: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            UnusableReplyCase(
                name="no_condition",
                data=GitCommitLogGetResponseData(),
                message="The worker answered without a condition",
            ),
            id="no_condition",
        ),
        pytest.param(
            UnusableReplyCase(
                name="contradictory_fields",
                data=GitCommitLogGetResponseData(
                    condition=RepositoryGitCondition.IN_SYNC,
                    unavailable_reason=RepositoryGitUnavailableReason.TIMEOUT,
                ),
                message="The worker answered with an inconsistent result: "
                "A result carrying an unavailable_reason must have condition UNAVAILABLE, not IN_SYNC",
            ),
            id="contradictory_fields",
        ),
        pytest.param(
            UnusableReplyCase(
                name="pending_count_without_behind",
                data=GitCommitLogGetResponseData(condition=RepositoryGitCondition.REWRITTEN, pending_count=3),
                message="The worker answered with an inconsistent result: "
                "A pending count is only reported under BEHIND, not REWRITTEN",
            ),
            id="pending_count_without_behind",
        ),
    ],
)
async def test_an_unusable_reply_raises_as_a_worker_failure(case: UnusableReplyCase) -> None:
    bus = RecordingRPCBus(replies=[GitCommitLogGetResponse(data=case.data)])
    reader = BusRepositoryGitStateReader(message_bus=bus, timeout=30)

    with pytest.raises(RPCError) as raised:
        await reader.commits(request=REQUEST)

    assert raised.value.message == case.message
