"""Convert the branch-heads read between its domain values and its message-bus form, in both directions."""

from __future__ import annotations

from infrahub.exceptions import RPCError
from infrahub.message_bus.messages.git_branch_heads_get import (
    BranchRefInput,
    GitBranchDriftRow,
    GitBranchHeadsGet,
    GitBranchHeadsGetResponseData,
)

from .models import BranchDriftResult, BranchDriftRow, BranchHeadsRequest, BranchRef


def request_to_message(request: BranchHeadsRequest) -> GitBranchHeadsGet:
    return GitBranchHeadsGet(
        repository_id=request.repository_id,
        repository_name=request.repository_name,
        repository_kind=request.repository_kind,
        location=request.location,
        branches=[
            BranchRefInput(branch_name=branch.branch_name, git_ref=branch.git_ref, tracked_commit=branch.tracked_commit)
            for branch in request.branches
        ],
    )


def message_to_request(message: GitBranchHeadsGet) -> BranchHeadsRequest:
    return BranchHeadsRequest(
        repository_id=message.repository_id,
        repository_name=message.repository_name,
        repository_kind=message.repository_kind,
        location=message.location,
        branches=tuple(
            BranchRef(branch_name=branch.branch_name, git_ref=branch.git_ref, tracked_commit=branch.tracked_commit)
            for branch in message.branches
        ),
    )


def result_to_response_data(result: BranchDriftResult) -> GitBranchHeadsGetResponseData:
    return GitBranchHeadsGetResponseData(
        fetched_at=result.fetched_at,
        unavailable_reason=result.unavailable_reason,
        warm_up_task_id=result.warm_up_task_id,
        branches=[
            GitBranchDriftRow(
                branch_name=row.branch_name,
                git_ref=row.git_ref,
                tracked_commit=row.tracked_commit,
                remote_head=row.remote_head,
                condition=row.condition,
            )
            for row in result.branches
        ],
        error_message=result.error_message,
    )


def response_data_to_result(data: GitBranchHeadsGetResponseData) -> BranchDriftResult:
    """Return the answer a worker reply carries.

    Raises:
        RPCError: When the reply carries fields that contradict each other.

    """
    try:
        return BranchDriftResult(
            branches=tuple(
                BranchDriftRow(
                    branch_name=row.branch_name,
                    git_ref=row.git_ref,
                    tracked_commit=row.tracked_commit,
                    remote_head=row.remote_head,
                    condition=row.condition,
                )
                for row in data.branches
            ),
            fetched_at=data.fetched_at,
            unavailable_reason=data.unavailable_reason,
            warm_up_task_id=data.warm_up_task_id,
            error_message=data.error_message,
        )
    except ValueError as exc:
        raise RPCError(message=f"The worker answered with an inconsistent result: {exc}") from exc
