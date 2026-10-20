from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.exceptions import GraphQLError, ServerNotReachableError
from infrahub_sdk.uuidt import UUIDT
from prefect import flow

from infrahub.exceptions import RepositoryConnectionError
from infrahub.git.activity.factory import build_repository_activity
from infrahub.git.tasks import git_branch_create
from infrahub.message_bus.messages import RefreshGitFetch
from tests.adapters.cache import MemoryCache, RecordingCache
from tests.adapters.message_bus import BusRecorder, FailingBus
from tests.helpers.git import LocalRemote, build_repository_client, clone_repository
from tests.helpers.repository_activity import (
    last_run_branches,
    run_record_operations,
    run_record_writes,
    stored_run_keys,
)

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
            activity=build_repository_activity(cache=MemoryCache()),
        )

    await create_branch()

    created_at = remote.repo.commit(CREATED_BRANCH).hexsha
    assert [
        (message.infrahub_branch_name, message.commit)
        for message in recorder.messages
        if isinstance(message, RefreshGitFetch)
    ] == [(CREATED_BRANCH, created_at)]


@dataclass
class ActivityRepository:
    name: str
    repository_id: str
    remote: LocalRemote


def _activity_repository(tmp_path: Path, name: str) -> ActivityRepository:
    return ActivityRepository(
        name=name,
        repository_id=str(UUIDT.new()),
        remote=LocalRemote.create(directory=tmp_path / name, trunk="main", branches=[]),
    )


async def _clone(repository: ActivityRepository) -> None:
    client = build_repository_client(
        repository_id=repository.repository_id,
        name=repository.name,
        location=str(repository.remote.directory),
        default_branch="main",
    )
    await clone_repository(
        id=repository.repository_id, name=repository.name, location=str(repository.remote.directory), client=client
    )


async def _create_branch_recording_activity(
    repository: ActivityRepository, cache: RecordingCache, message_bus: BusRecorder | None = None
) -> None:
    client = build_repository_client(
        repository_id=repository.repository_id,
        name=repository.name,
        location=str(repository.remote.directory),
        default_branch="main",
    )

    @flow(name="test-git-branch-create-activity")
    async def create_branch() -> None:
        await git_branch_create(
            client=client,
            branch=CREATED_BRANCH,
            branch_id=f"{CREATED_BRANCH}-id",
            repository_id=repository.repository_id,
            repository_name=repository.name,
            repository_location=str(repository.remote.directory),
            message_bus=message_bus or BusRecorder(),
            activity=build_repository_activity(cache=cache),
        )

    await create_branch()


async def test_creating_a_branch_records_its_run_and_the_branch_as_imported(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
) -> None:
    repository = _activity_repository(tmp_path=tmp_path, name="activity-branch-create-repo")
    await _clone(repository)
    cache = RecordingCache()

    await _create_branch_recording_activity(repository=repository, cache=cache)

    assert run_record_operations(cache=cache, repository_id=repository.repository_id) == {"branch_create"}
    assert run_record_writes(cache=cache, repository_id=repository.repository_id) == [(None, None)]
    assert stored_run_keys(cache=cache, repository_id=repository.repository_id) == []
    assert last_run_branches(cache=cache, repository_id=repository.repository_id, operation="branch_create") == [
        {"branch_name": CREATED_BRANCH, "outcome": "imported"}
    ]


async def test_a_branch_that_already_exists_in_git_lists_no_branch(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
) -> None:
    repository = _activity_repository(tmp_path=tmp_path, name="activity-existing-branch-repo")
    await _clone(repository)
    await _create_branch_recording_activity(repository=repository, cache=RecordingCache())
    cache = RecordingCache()

    await _create_branch_recording_activity(repository=repository, cache=cache)

    assert stored_run_keys(cache=cache, repository_id=repository.repository_id) == []
    assert last_run_branches(cache=cache, repository_id=repository.repository_id, operation="branch_create") == []


async def test_a_repository_that_cannot_be_read_records_the_branch_as_failed(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
) -> None:
    """The repository cannot be cloned on this worker, so the task skips it without raising."""
    repository = _activity_repository(tmp_path=tmp_path, name="activity-unread-repo")
    shutil.rmtree(repository.remote.directory)
    cache = RecordingCache()

    await _create_branch_recording_activity(repository=repository, cache=cache)

    assert run_record_writes(cache=cache, repository_id=repository.repository_id) == [(None, None)]
    assert stored_run_keys(cache=cache, repository_id=repository.repository_id) == []
    assert last_run_branches(cache=cache, repository_id=repository.repository_id, operation="branch_create") == [
        {"branch_name": CREATED_BRANCH, "outcome": "failed"}
    ]


async def test_a_branch_that_cannot_be_pushed_records_the_branch_as_failed(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
) -> None:
    name = "activity-unreachable-remote-repo"
    repository = _activity_repository(tmp_path=tmp_path, name=name)
    await _clone(repository)
    shutil.rmtree(repository.remote.directory)
    cache = RecordingCache()

    with pytest.raises(
        RepositoryConnectionError,
        match=rf"^Unable to push to the remote of repository {name}, please check that the remote is reachable\.$",
    ):
        await _create_branch_recording_activity(repository=repository, cache=cache)

    assert stored_run_keys(cache=cache, repository_id=repository.repository_id) == []
    assert last_run_branches(cache=cache, repository_id=repository.repository_id, operation="branch_create") == [
        {"branch_name": CREATED_BRANCH, "outcome": "failed"}
    ]


async def test_a_pushed_branch_whose_broadcast_fails_stays_imported(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
) -> None:
    repository = _activity_repository(tmp_path=tmp_path, name="activity-failed-broadcast-repo")
    await _clone(repository)
    cache = RecordingCache()

    with pytest.raises(ConnectionError, match=r"^The message bus cannot be reached$"):
        await _create_branch_recording_activity(repository=repository, cache=cache, message_bus=FailingBus())

    assert [branch.name for branch in repository.remote.repo.branches] == [CREATED_BRANCH, "main"]
    assert last_run_branches(cache=cache, repository_id=repository.repository_id, operation="branch_create") == [
        {"branch_name": CREATED_BRANCH, "outcome": "imported"}
    ]
