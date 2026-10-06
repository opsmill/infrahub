from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.exceptions import GraphQLError, ServerNotReachableError
from infrahub_sdk.uuidt import UUIDT
from prefect import flow

from infrahub.git.tasks import git_branch_create
from infrahub.message_bus.messages import RefreshGitFetch
from tests.adapters.message_bus import BusRecorder
from tests.helpers.git import LocalRemote, build_repository_client, clone_repository

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.database import InfrahubDatabase

REPOSITORY_NAME = "branch-create-repo"
CREATED_BRANCH = "created-branch"


@dataclass
class CommitWriteFailureCase:
    name: str
    error: SdkError


COMMIT_WRITE_FAILURE_CASES: list[CommitWriteFailureCase] = [
    CommitWriteFailureCase(
        name="the_graph_refuses_the_commit",
        error=GraphQLError(errors=[{"message": "The commit update was rejected"}]),
    ),
    CommitWriteFailureCase(
        name="the_server_cannot_be_reached",
        error=ServerNotReachableError(address="http://mock"),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in COMMIT_WRITE_FAILURE_CASES])
async def test_a_new_branch_is_announced_even_when_its_commit_cannot_be_recorded(
    case: CommitWriteFailureCase,
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
) -> None:
    """The next sync records a commit the graph lacks, but nothing announces the branch to the other workers again."""
    remote = LocalRemote.create(directory=tmp_path / "remote", trunk="main", branches=[])
    repository_id = str(UUIDT.new())
    client = build_repository_client(
        repository_id=repository_id,
        name=REPOSITORY_NAME,
        location=str(remote.directory),
        default_branch="main",
        commit_update_error=case.error,
    )
    await clone_repository(
        id=repository_id,
        name=REPOSITORY_NAME,
        location=str(remote.directory),
        client=client,
        update_commit_value=False,
    )
    recorder = BusRecorder()

    @flow(name="test-git-branch-create")
    async def create_branch() -> None:
        await git_branch_create(
            client=client,
            branch=CREATED_BRANCH,
            branch_id=f"{CREATED_BRANCH}-id",
            repository_id=repository_id,
            repository_name=REPOSITORY_NAME,
            repository_location=str(remote.directory),
            message_bus=recorder,
        )

    await create_branch()

    created_at = remote.repo.commit(CREATED_BRANCH).hexsha
    assert [
        (message.infrahub_branch_name, message.commit)
        for message in recorder.messages
        if isinstance(message, RefreshGitFetch)
    ] == [(CREATED_BRANCH, created_at)]
