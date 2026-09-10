from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.core.constants import (
    InfrahubKind,
    RepositoryCommitState,
    RepositoryGitCondition,
    RepositoryGitUnavailableReason,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.git.state.models import CommitEntry, CommitLogRequest, CommitLogResult
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_query
from tests.helpers.repository_git_state import RecordingRepositoryGitStateReader

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

REPOSITORY_NAME = "test-commit-visibility"
REPOSITORY_LOCATION = "/tmp/test-commit-visibility"
REPOSITORY_DEFAULT_BRANCH = "trunk"
MAIN_COMMIT = "1111111111111111111111111111111111111111"
BRANCH_COMMIT = "2222222222222222222222222222222222222222"
REMOTE_HEAD = "3333333333333333333333333333333333333333"
FETCHED_AT = datetime(2026, 9, 8, 10, 30, tzinfo=UTC)

COMMITS_QUERY = """
query RepositoryCommits($id: String!, $limit: Int, $offset: Int) {
  InfrahubRepositoryCommits(repository_id: $id, limit: $limit, offset: $offset) {
    repository_id
    branch_name
    git_ref
    condition
    imported_commit
    remote_head
    pending_count
    fetched_at
    checked_at
    unavailable { reason message warm_up_task_id }
    edges { node { hash short_hash summary message author_name authored_at committed_at state } }
  }
}
"""

COMMITS_QUERY_WITHOUT_PENDING_COUNT = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id) {
    condition
    remote_head
    edges { node { hash state } }
  }
}
"""

COMMITS_QUERY_INFRAHUB_SIDE_ONLY = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id) {
    repository_id
    branch_name
    git_ref
    imported_commit
    checked_at
  }
}
"""

COMMITS_QUERY_SELECTED_TWICE = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id) {
    repository_id
  }
  InfrahubRepositoryCommits(repository_id: $id) {
    condition
  }
}
"""

DRIFT_QUERY = """
query RepositoryBranchDrift($id: String!) {
  InfrahubRepositoryBranchDrift(repository_id: $id) {
    repository_id
    fetched_at
    checked_at
    unavailable { reason message warm_up_task_id }
    edges { node { branch_name git_ref tracked_commit remote_head condition } }
  }
}
"""


@pytest.fixture
async def repository(db: InfrahubDatabase, default_branch: Branch, create_test_admin: Node) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(
        db=db,
        name=REPOSITORY_NAME,
        location=REPOSITORY_LOCATION,
        default_branch=REPOSITORY_DEFAULT_BRANCH,
        commit=MAIN_COMMIT,
    )
    await repo.save(db=db)
    return repo


@pytest.fixture
async def service(db: InfrahubDatabase) -> InfrahubServices:
    return await InfrahubServices.new(database=db, message_bus=BusRecorder())


@pytest.fixture
def recording_reader() -> Iterator[RecordingRepositoryGitStateReader]:
    reader = RecordingRepositoryGitStateReader()
    original = config.OVERRIDE.repository_git_state_reader
    config.OVERRIDE.repository_git_state_reader = reader
    yield reader
    config.OVERRIDE.repository_git_state_reader = original


@pytest.fixture
async def synced_branch(db: InfrahubDatabase, default_branch: Branch, repository: Node) -> Branch:
    branch = await create_branch(branch_name="branch2", db=db)
    branch.sync_with_git = True
    await branch.save(db=db)

    repo_on_branch = await NodeManager.get_one(db=db, id=repository.id, branch=branch, raise_on_error=True)
    repo_on_branch.commit.value = BRANCH_COMMIT
    await repo_on_branch.save(db=db)

    return branch


@pytest.fixture
async def unsynced_branch(db: InfrahubDatabase, default_branch: Branch, repository: Node) -> Branch:
    branch = await create_branch(branch_name="branch2", db=db)

    repo_on_branch = await NodeManager.get_one(db=db, id=repository.id, branch=branch, raise_on_error=True)
    repo_on_branch.commit.value = BRANCH_COMMIT
    await repo_on_branch.save(db=db)

    return branch


@pytest.fixture
def no_import_filters() -> Iterator[None]:
    """Import every remote branch, whatever INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES holds in the ambient environment."""
    original = config.SETTINGS.git.import_sync_branch_names
    config.SETTINGS.git.import_sync_branch_names = []
    yield
    config.SETTINGS.git.import_sync_branch_names = original


@pytest.fixture
def import_filters_excluding_branch2() -> Iterator[None]:
    original = config.SETTINGS.git.import_sync_branch_names
    config.SETTINGS.git.import_sync_branch_names = ["release-.*"]
    yield
    config.SETTINGS.git.import_sync_branch_names = original


def _expected_request(
    repository_id: str,
    infrahub_branch_name: str,
    git_ref: str,
    imported_commit: str,
    include_pending_count: bool,
    limit: int = 10,
    offset: int = 0,
) -> CommitLogRequest:
    return CommitLogRequest(
        repository_id=repository_id,
        repository_name=REPOSITORY_NAME,
        repository_kind=InfrahubKind.REPOSITORY,
        location=REPOSITORY_LOCATION,
        infrahub_branch_name=infrahub_branch_name,
        git_ref=git_ref,
        imported_commit=imported_commit,
        limit=limit,
        offset=offset,
        include_pending_count=include_pending_count,
    )


async def test_commit_log_answers_the_infrahub_side_fields_for_the_request_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    recording_reader.commit_results.append(
        CommitLogResult(
            condition=RepositoryGitCondition.BEHIND,
            remote_head=REMOTE_HEAD,
            imported_commit=MAIN_COMMIT,
            pending_count=2,
            fetched_at=FETCHED_AT,
            commits=(
                CommitEntry(
                    hash=REMOTE_HEAD,
                    short_hash=REMOTE_HEAD[:7],
                    summary="Add a widget",
                    message="Add a widget\n\nWith a body.",
                    author_name="Ada Lovelace",
                    authored_at=FETCHED_AT,
                    committed_at=FETCHED_AT,
                    state=RepositoryCommitState.HEAD,
                ),
            ),
        )
    )

    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryCommits"] == {
        "repository_id": repository.id,
        "branch_name": default_branch.name,
        "git_ref": REPOSITORY_DEFAULT_BRANCH,
        "condition": "BEHIND",
        "imported_commit": MAIN_COMMIT,
        "remote_head": REMOTE_HEAD,
        "pending_count": 2,
        "fetched_at": FETCHED_AT.isoformat(),
        "checked_at": None,
        "unavailable": None,
        "edges": [
            {
                "node": {
                    "hash": REMOTE_HEAD,
                    "short_hash": REMOTE_HEAD[:7],
                    "summary": "Add a widget",
                    "message": "Add a widget\n\nWith a body.",
                    "author_name": "Ada Lovelace",
                    "authored_at": FETCHED_AT.isoformat(),
                    "committed_at": FETCHED_AT.isoformat(),
                    "state": "HEAD",
                }
            }
        ],
    }


async def test_drift_answers_the_infrahub_side_fields(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
) -> None:
    response = await graphql_query(
        query=DRIFT_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryBranchDrift"] == {
        "repository_id": repository.id,
        "fetched_at": None,
        "checked_at": None,
        "unavailable": {
            "reason": "NOT_IMPLEMENTED",
            "message": "Reading git state from a worker is not available in this version.",
            "warm_up_task_id": None,
        },
        "edges": [],
    }


async def test_commit_log_follows_the_infrahub_branch(
    db: InfrahubDatabase,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    synced_branch: Branch,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=synced_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    answer = response.data["InfrahubRepositoryCommits"]
    assert answer["branch_name"] == synced_branch.name
    assert answer["git_ref"] == synced_branch.name
    assert answer["imported_commit"] == BRANCH_COMMIT
    assert recording_reader.commit_requests == [
        _expected_request(
            repository_id=repository.id,
            infrahub_branch_name=synced_branch.name,
            git_ref=synced_branch.name,
            imported_commit=BRANCH_COMMIT,
            include_pending_count=True,
        )
    ]


async def test_commit_log_tracks_a_branch_that_does_not_sync_with_git(
    db: InfrahubDatabase,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    unsynced_branch: Branch,
    no_import_filters: None,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=unsynced_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    answer = response.data["InfrahubRepositoryCommits"]
    assert answer["git_ref"] == unsynced_branch.name
    assert answer["imported_commit"] == BRANCH_COMMIT
    assert recording_reader.commit_requests == [
        _expected_request(
            repository_id=repository.id,
            infrahub_branch_name=unsynced_branch.name,
            git_ref=unsynced_branch.name,
            imported_commit=BRANCH_COMMIT,
            include_pending_count=True,
        )
    ]


async def test_commit_log_reports_a_branch_the_import_filters_skip_as_untracked(
    db: InfrahubDatabase,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    unsynced_branch: Branch,
    import_filters_excluding_branch2: None,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=unsynced_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    answer = response.data["InfrahubRepositoryCommits"]
    assert answer["git_ref"] is None
    assert answer["condition"] == RepositoryGitCondition.NOT_TRACKED.name
    assert answer["edges"] == []
    assert recording_reader.commit_requests == []


@dataclass
class PagingCase:
    name: str
    variables: dict[str, Any]
    message: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            PagingCase(name="limit_zero", variables={"limit": 0}, message="limit must be between 1 and 100"),
            id="limit_zero",
        ),
        pytest.param(
            PagingCase(name="limit_above_max", variables={"limit": 101}, message="limit must be between 1 and 100"),
            id="limit_above_max",
        ),
        pytest.param(
            PagingCase(
                name="negative_offset",
                variables={"offset": -1},
                message="offset must be greater than or equal to 0",
            ),
            id="negative_offset",
        ),
    ],
)
async def test_commit_log_refuses_out_of_range_paging(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
    case: PagingCase,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id, **case.variables},
        account_session=session_admin,
    )

    assert response.errors
    assert response.errors[0].message == case.message
    assert recording_reader.commit_requests == []


async def test_explicit_null_paging_falls_back_to_the_documented_defaults(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    """Both arguments are nullable, so an explicit null must mean the default rather than raising."""
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id, "limit": None, "offset": None},
        account_session=session_admin,
    )

    assert not response.errors
    assert recording_reader.commit_requests == [
        _expected_request(
            repository_id=repository.id,
            infrahub_branch_name=default_branch.name,
            git_ref=REPOSITORY_DEFAULT_BRANCH,
            imported_commit=MAIN_COMMIT,
            include_pending_count=True,
            limit=10,
            offset=0,
        )
    ]


async def test_selecting_pending_count_asks_the_reader_to_count(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert recording_reader.commit_requests == [
        _expected_request(
            repository_id=repository.id,
            infrahub_branch_name=default_branch.name,
            git_ref=REPOSITORY_DEFAULT_BRANCH,
            imported_commit=MAIN_COMMIT,
            include_pending_count=True,
        )
    ]


async def test_omitting_pending_count_leaves_the_count_unrequested(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY_WITHOUT_PENDING_COUNT,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert recording_reader.commit_requests == [
        _expected_request(
            repository_id=repository.id,
            infrahub_branch_name=default_branch.name,
            git_ref=REPOSITORY_DEFAULT_BRANCH,
            imported_commit=MAIN_COMMIT,
            include_pending_count=False,
        )
    ]


async def test_infrahub_side_only_selection_makes_no_request(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY_INFRAHUB_SIDE_ONLY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryCommits"] == {
        "repository_id": repository.id,
        "branch_name": default_branch.name,
        "git_ref": REPOSITORY_DEFAULT_BRANCH,
        "imported_commit": MAIN_COMMIT,
        "checked_at": None,
    }
    assert recording_reader.commit_requests == []
    assert recording_reader.branch_heads_requests == []


async def test_a_root_field_selected_twice_still_answers_every_selection(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    no_import_filters: None,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY_SELECTED_TWICE,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryCommits"] == {
        "repository_id": repository.id,
        "condition": RepositoryGitCondition.NOT_TRACKED.name,
    }
    assert recording_reader.commit_requests == [
        _expected_request(
            repository_id=repository.id,
            infrahub_branch_name=default_branch.name,
            git_ref=REPOSITORY_DEFAULT_BRANCH,
            imported_commit=MAIN_COMMIT,
            include_pending_count=False,
        )
    ]


async def test_commit_log_reports_the_unavailable_placeholder(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    answer = response.data["InfrahubRepositoryCommits"]
    assert answer["condition"] == RepositoryGitCondition.UNAVAILABLE.name
    assert answer["unavailable"] == {
        "reason": RepositoryGitUnavailableReason.NOT_IMPLEMENTED.name,
        "message": "Reading git state from a worker is not available in this version.",
        "warm_up_task_id": None,
    }
    assert answer["edges"] == []
    assert answer["remote_head"] is None
    assert answer["pending_count"] is None
