"""Convert the commit-log read between its domain values and its message-bus form, in both directions."""

from __future__ import annotations

from infrahub.exceptions import RPCError
from infrahub.message_bus.messages.git_commit_log_get import (
    GitCommitLogEntry,
    GitCommitLogGet,
    GitCommitLogGetResponseData,
)

from .models import CommitEntry, CommitLogRequest, CommitLogResult


def request_to_message(request: CommitLogRequest) -> GitCommitLogGet:
    return GitCommitLogGet(
        repository_id=request.repository_id,
        repository_name=request.repository_name,
        repository_kind=request.repository_kind,
        location=request.location,
        infrahub_branch_name=request.infrahub_branch_name,
        git_ref=request.git_ref,
        imported_commit=request.imported_commit,
        limit=request.limit,
        offset=request.offset,
        include_pending_count=request.include_pending_count,
    )


def message_to_request(message: GitCommitLogGet) -> CommitLogRequest:
    return CommitLogRequest(
        repository_id=message.repository_id,
        repository_name=message.repository_name,
        repository_kind=message.repository_kind,
        location=message.location,
        infrahub_branch_name=message.infrahub_branch_name,
        git_ref=message.git_ref,
        imported_commit=message.imported_commit,
        limit=message.limit,
        offset=message.offset,
        include_pending_count=message.include_pending_count,
    )


def result_to_response_data(result: CommitLogResult) -> GitCommitLogGetResponseData:
    return GitCommitLogGetResponseData(
        condition=result.condition,
        remote_head=result.remote_head,
        imported_commit=result.imported_commit,
        pending_count=result.pending_count,
        fetched_at=result.fetched_at,
        unavailable_reason=result.unavailable_reason,
        warm_up_task_id=result.warm_up_task_id,
        commits=[
            GitCommitLogEntry(
                hash=entry.hash,
                message=entry.message,
                author_name=entry.author_name,
                authored_at=entry.authored_at,
                committed_at=entry.committed_at,
                state=entry.state,
            )
            for entry in result.commits
        ],
        error_message=result.error_message,
    )


def response_data_to_result(data: GitCommitLogGetResponseData) -> CommitLogResult:
    """Return the answer a worker reply carries.

    Raises:
        RPCError: When the reply carries no condition, or fields that contradict each other.

    """
    if data.condition is None:
        raise RPCError(message="The worker answered without a condition")

    try:
        return CommitLogResult(
            condition=data.condition,
            remote_head=data.remote_head,
            imported_commit=data.imported_commit,
            pending_count=data.pending_count,
            commits=tuple(
                CommitEntry(
                    hash=entry.hash,
                    message=entry.message,
                    author_name=entry.author_name,
                    authored_at=entry.authored_at,
                    committed_at=entry.committed_at,
                    state=entry.state,
                )
                for entry in data.commits
            ),
            fetched_at=data.fetched_at,
            unavailable_reason=data.unavailable_reason,
            warm_up_task_id=data.warm_up_task_id,
            error_message=data.error_message,
        )
    except ValueError as exc:
        raise RPCError(message=f"The worker answered with an inconsistent result: {exc}") from exc
