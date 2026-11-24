from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

from infrahub.core.constants import InfrahubKind, RepositoryCommitState, RepositoryGitCondition
from infrahub.git.state.commit_log_wire import (
    message_to_request,
    request_to_message,
    response_data_to_result,
    result_to_response_data,
)
from infrahub.git.state.models import CommitEntry, CommitLogRequest, CommitLogResult
from infrahub.message_bus.messages.git_commit_log_get import (
    GitCommitLogEntry,
    GitCommitLogGet,
    GitCommitLogGetResponseData,
)

AUTHORED_AT = datetime(2026, 9, 8, 10, 30, tzinfo=UTC)
COMMITTED_AT = datetime(2026, 9, 8, 10, 45, tzinfo=UTC)


def test_a_request_survives_the_round_trip() -> None:
    request = CommitLogRequest(
        repository_id="18d39e83-0000-0000-0000-000000000001",
        repository_name="edge",
        repository_kind=InfrahubKind.READONLYREPOSITORY,
        location="https://git.example.com/edge.git",
        infrahub_branch_name="branch2",
        git_ref="v1.0",
        imported_commit="1111111111111111111111111111111111111111",
        limit=25,
        offset=50,
        include_pending_count=True,
    )

    assert message_to_request(message=request_to_message(request=request)) == request


def test_a_result_survives_the_round_trip() -> None:
    result = CommitLogResult(
        condition=RepositoryGitCondition.BEHIND,
        remote_head="3333333333333333333333333333333333333333",
        imported_commit="1111111111111111111111111111111111111111",
        pending_count=4,
        commits=(
            CommitEntry(
                hash="3333333333333333333333333333333333333333",
                message="Add a widget\n\nWith a body.",
                author_name="Ada Lovelace",
                authored_at=AUTHORED_AT,
                committed_at=COMMITTED_AT,
                state=RepositoryCommitState.HEAD,
            ),
        ),
        fetched_at=COMMITTED_AT,
    )

    assert response_data_to_result(data=result_to_response_data(result=result)) == result


def test_the_wire_models_carry_every_domain_field() -> None:
    """A field added on one side and not the other would otherwise be dropped silently in transit."""
    assert set(GitCommitLogGet.model_fields) - {"meta"} == {field.name for field in fields(CommitLogRequest)}
    assert set(GitCommitLogGetResponseData.model_fields) == {field.name for field in fields(CommitLogResult)}
    assert set(GitCommitLogEntry.model_fields) == {field.name for field in fields(CommitEntry)}
