from __future__ import annotations

import json
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
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError, WorkerTimeoutError
from infrahub.git.state.cache_keys import activity_last_run_key, activity_run_key, refs_check_last_key
from infrahub.git.state.models import (
    CommitEntry,
    CommitLogRequest,
    CommitLogResult,
)
from infrahub.git.state.reader import UnavailableRepositoryGitStateReader
from infrahub.graphql.error_formatter import format_graphql_errors
from infrahub.graphql.queries.repository_git_state import _resolve_git_ref
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.redis import RedisCache
from tests.adapters.cache import MemoryCache, UnreachableCache
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_query
from tests.helpers.repository_git_state import FailingRepositoryGitStateReader, RecordingRepositoryGitStateReader

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

REPOSITORY_NAME = "test-commit-visibility"
REPOSITORY_LOCATION = "/tmp/test-commit-visibility"
REPOSITORY_DEFAULT_BRANCH = "trunk"
READ_ONLY_REPOSITORY_NAME = "test-commit-visibility-read-only"
READ_ONLY_REPOSITORY_LOCATION = "/tmp/test-commit-visibility-read-only"
READ_ONLY_REF = "v1.0"
CHECKED_AT = datetime(2026, 9, 8, 11, 45, tzinfo=UTC)
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
    unavailable { reason message }
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

COMMITS_QUERY_THROUGH_A_FRAGMENT = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id) {
    repository_id
    ...GitState
  }
}

fragment GitState on RepositoryCommits {
  condition
  remote_head
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
async def read_only_repository(db: InfrahubDatabase, default_branch: Branch, create_test_admin: Node) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await repo.new(
        db=db,
        name=READ_ONLY_REPOSITORY_NAME,
        location=READ_ONLY_REPOSITORY_LOCATION,
        ref=READ_ONLY_REF,
        commit=MAIN_COMMIT,
    )
    await repo.save(db=db)
    return repo


@pytest.fixture
async def repository_without_default_branch(
    db: InfrahubDatabase, default_branch: Branch, create_test_admin: Node
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(db=db, name=REPOSITORY_NAME, location=REPOSITORY_LOCATION, default_branch="", commit=MAIN_COMMIT)
    await repo.save(db=db)
    return repo


@pytest.fixture
async def service(db: InfrahubDatabase) -> InfrahubServices:
    return await InfrahubServices.new(database=db, message_bus=BusRecorder(), cache=MemoryCache())


@pytest.fixture
def recording_reader() -> Iterator[RecordingRepositoryGitStateReader]:
    reader = RecordingRepositoryGitStateReader()
    original = config.OVERRIDE.repository_git_state_reader
    config.OVERRIDE.repository_git_state_reader = reader
    yield reader
    config.OVERRIDE.repository_git_state_reader = original


@pytest.fixture
def unavailable_reader() -> Iterator[UnavailableRepositoryGitStateReader]:
    reader = UnavailableRepositoryGitStateReader()
    original = config.OVERRIDE.repository_git_state_reader
    config.OVERRIDE.repository_git_state_reader = reader
    yield reader
    config.OVERRIDE.repository_git_state_reader = original


@pytest.fixture
def timing_out_reader() -> Iterator[FailingRepositoryGitStateReader]:
    reader = FailingRepositoryGitStateReader(
        error=WorkerTimeoutError(operation="git.commit_log.get", timeout_seconds=30)
    )
    original = config.OVERRIDE.repository_git_state_reader
    config.OVERRIDE.repository_git_state_reader = reader
    yield reader
    config.OVERRIDE.repository_git_state_reader = original


@pytest.fixture
async def service_with_cache(db: InfrahubDatabase) -> tuple[InfrahubServices, MemoryCache]:
    cache = MemoryCache()
    return await InfrahubServices.new(database=db, message_bus=BusRecorder(), cache=cache), cache


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


async def test_commit_log_answers_as_of_the_requested_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
) -> None:
    """The repository node is read at `at` too, not only the per-branch values."""
    before_the_later_import = Timestamp()
    repo = await NodeManager.get_one(db=db, id=repository.id, branch=default_branch, raise_on_error=True)
    repo.commit.value = REMOTE_HEAD
    await repo.save(db=db)

    reloaded = await NodeManager.get_one(db=db, id=repository.id, branch=default_branch, raise_on_error=True)
    assert reloaded.commit.value == REMOTE_HEAD

    response = await graphql_query(
        query=COMMITS_QUERY_INFRAHUB_SIDE_ONLY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
        at=before_the_later_import,
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


async def test_commit_log_reports_a_repository_with_no_default_branch_as_untracked(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository_without_default_branch: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository_without_default_branch.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    answer = response.data["InfrahubRepositoryCommits"]
    assert answer["git_ref"] is None
    assert answer["imported_commit"] == MAIN_COMMIT
    assert answer["condition"] == RepositoryGitCondition.NOT_TRACKED.name
    assert answer["edges"] == []
    assert recording_reader.commit_requests == []


async def test_reading_git_state_refuses_a_kind_with_no_git_state(
    db: InfrahubDatabase, default_branch: Branch, create_test_admin: Node
) -> None:
    """Both concrete repository kinds are handled, so this pins what a third one would surface."""
    with pytest.raises(ValidationError, match=r"^Reading git state is not supported for a CoreAccount$"):
        _resolve_git_ref(
            repository=create_test_admin,
            infrahub_branch_name=default_branch.name,
            branch_is_synced_with_git=False,
        )


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


async def test_git_fields_reached_through_a_fragment_still_ask_the_reader(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    no_import_filters: None,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    """A fragment is how a generated client selects fields, and the gate reads the selection."""
    response = await graphql_query(
        query=COMMITS_QUERY_THROUGH_A_FRAGMENT,
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
        "remote_head": None,
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
    unavailable_reader: UnavailableRepositoryGitStateReader,
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
    }
    assert answer["edges"] == []
    assert answer["remote_head"] is None
    assert answer["pending_count"] is None


async def test_commit_log_surfaces_a_worker_timeout_with_its_retry_hint(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service: InfrahubServices,
    repository: Node,
    timing_out_reader: FailingRepositoryGitStateReader,
) -> None:
    """The commit log has nothing to show without a worker answer, so a timeout is an error, not a state."""
    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session_admin,
    )

    assert response.data is None
    assert response.errors
    assert format_graphql_errors(errors=response.errors) == [
        {
            "message": "No worker answered git.commit_log.get within 30 seconds",
            "locations": [{"line": 3, "column": 3}],
            "path": ["InfrahubRepositoryCommits"],
            "extensions": {
                "code": "WORKER_TIMEOUT",
                "http_status": 504,
                "data": {"operation": "git.commit_log.get", "timeout_seconds": 30, "retry_after_seconds": 30},
            },
        }
    ]


async def test_commit_log_reports_when_a_read_only_remote_was_last_checked(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    read_only_repository: Node,
    recording_reader: RecordingRepositoryGitStateReader,
) -> None:
    service, cache = service_with_cache
    await cache.set(key=refs_check_last_key(repository_id=read_only_repository.id), value=CHECKED_AT.isoformat())

    response = await graphql_query(
        query=COMMITS_QUERY_INFRAHUB_SIDE_ONLY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": read_only_repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryCommits"] == {
        "repository_id": read_only_repository.id,
        "branch_name": default_branch.name,
        "git_ref": READ_ONLY_REF,
        "imported_commit": MAIN_COMMIT,
        "checked_at": CHECKED_AT.isoformat(),
    }
    assert recording_reader.commit_requests == []


@dataclass
class UnknownCheckTimeCase:
    name: str
    cached_value: str | None


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(UnknownCheckTimeCase(name="never_checked", cached_value=None), id="never_checked"),
        pytest.param(UnknownCheckTimeCase(name="unreadable_value", cached_value="not-a-date"), id="unreadable_value"),
    ],
)
async def test_a_read_only_remote_with_no_readable_check_reports_no_check_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    read_only_repository: Node,
    case: UnknownCheckTimeCase,
) -> None:
    service, cache = service_with_cache
    if case.cached_value is not None:
        await cache.set(key=refs_check_last_key(repository_id=read_only_repository.id), value=case.cached_value)

    response = await graphql_query(
        query=COMMITS_QUERY_INFRAHUB_SIDE_ONLY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": read_only_repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryCommits"]["checked_at"] is None


async def test_an_unreachable_cache_leaves_the_query_answered_without_a_check_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    read_only_repository: Node,
) -> None:
    service = await InfrahubServices.new(database=db, message_bus=BusRecorder(), cache=UnreachableCache())

    response = await graphql_query(
        query=COMMITS_QUERY_INFRAHUB_SIDE_ONLY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": read_only_repository.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubRepositoryCommits"] == {
        "repository_id": read_only_repository.id,
        "branch_name": default_branch.name,
        "git_ref": READ_ONLY_REF,
        "imported_commit": MAIN_COMMIT,
        "checked_at": None,
    }


async def test_a_read_write_repository_never_reports_a_check_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    repository: Node,
) -> None:
    """Its sync fetches the remote, so a check time recorded against it is ignored."""
    service, cache = service_with_cache
    await cache.set(key=refs_check_last_key(repository_id=repository.id), value=CHECKED_AT.isoformat())

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
    assert response.data["InfrahubRepositoryCommits"]["checked_at"] is None


ACTIVITY_QUERY = """
query RepositoryActivity($id: String!) {
  InfrahubRepositoryActivity(id: $id) {
    repository_id
    active_runs { edges { node { run_id operation phase branch_name worker_id started_at updated_at } } }
    last_runs { edges { node { operation started_at finished_at branches { edges { node { branch_name outcome } } } } } }
    lock { worker_id requested_at }
  }
}
"""


def activity_run_record(
    repository_id: str, run_id: str, started_at: str, phase: str | None, branch_name: str | None
) -> str:
    return json.dumps(
        {
            "run_id": run_id,
            "repository_id": repository_id,
            "operation": "sync",
            "phase": phase,
            "branch_name": branch_name,
            "worker_id": "worker-1",
            "started_at": started_at,
            "updated_at": started_at,
        }
    )


def last_run_record(operation: str, finished_at: str, branches: list[tuple[str, str]]) -> str:
    return json.dumps(
        {
            "operation": operation,
            "started_at": "2026-09-08T09:00:00Z",
            "finished_at": finished_at,
            "branches": [{"branch_name": name, "outcome": outcome} for name, outcome in branches],
        }
    )


class ExpiringOnReadCache(MemoryCache):
    """Lists every key, then reads the keys in `expire_on_read` as expired, as when a record expires in between."""

    def __init__(self) -> None:
        super().__init__()
        self.expire_on_read: set[str] = set()

    async def get_values(self, keys: list[str]) -> list[str | None]:
        return [None if key in self.expire_on_read else self.storage.get(key) for key in keys]


async def query_activity(
    db: InfrahubDatabase, branch: Branch, service: InfrahubServices, session: AccountSession, repository_id: str
) -> dict[str, Any]:
    response = await graphql_query(
        query=ACTIVITY_QUERY,
        db=db,
        branch=branch,
        service=service,
        variables={"id": repository_id},
        account_session=session,
    )
    assert not response.errors
    assert response.data
    return response.data["InfrahubRepositoryActivity"]


async def test_activity_of_an_idle_repository_on_redis(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    repository: Node,
    redis: dict[int, int] | None,
) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")
    service = await InfrahubServices.new(database=db, message_bus=BusRecorder(), cache=RedisCache())

    activity = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=repository.id
    )

    assert activity == {
        "repository_id": repository.id,
        "active_runs": {"edges": []},
        "last_runs": {"edges": []},
        "lock": None,
    }


async def test_activity_lists_every_run_working_on_the_repository_oldest_first(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    repository: Node,
) -> None:
    service, cache = service_with_cache
    cache.storage[activity_run_key(repository_id=repository.id, run_id="run-b")] = activity_run_record(
        repository_id=repository.id,
        run_id="run-b",
        started_at="2026-09-08T10:05:00Z",
        phase="building",
        branch_name=default_branch.name,
    )
    cache.storage[activity_run_key(repository_id=repository.id, run_id="run-a")] = activity_run_record(
        repository_id=repository.id,
        run_id="run-a",
        started_at="2026-09-08T10:00:00Z",
        phase="fetching",
        branch_name=None,
    )
    cache.storage[activity_run_key(repository_id="other-repository", run_id="run-c")] = activity_run_record(
        repository_id="other-repository",
        run_id="run-c",
        started_at="2026-09-08T10:00:00Z",
        phase=None,
        branch_name=None,
    )

    activity = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=repository.id
    )

    assert activity["active_runs"] == {
        "edges": [
            {
                "node": {
                    "run_id": "run-a",
                    "operation": "SYNC",
                    "phase": "FETCHING",
                    "branch_name": None,
                    "worker_id": "worker-1",
                    "started_at": "2026-09-08T10:00:00+00:00",
                    "updated_at": "2026-09-08T10:00:00+00:00",
                }
            },
            {
                "node": {
                    "run_id": "run-b",
                    "operation": "SYNC",
                    "phase": "BUILDING",
                    "branch_name": default_branch.name,
                    "worker_id": "worker-1",
                    "started_at": "2026-09-08T10:05:00+00:00",
                    "updated_at": "2026-09-08T10:05:00+00:00",
                }
            },
        ]
    }


async def test_activity_skips_a_run_that_expires_between_listing_and_reading(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    repository: Node,
) -> None:
    cache = ExpiringOnReadCache()
    service = await InfrahubServices.new(database=db, message_bus=BusRecorder(), cache=cache)
    for run_id in ("run-kept", "run-expired"):
        cache.storage[activity_run_key(repository_id=repository.id, run_id=run_id)] = activity_run_record(
            repository_id=repository.id,
            run_id=run_id,
            started_at="2026-09-08T10:00:00Z",
            phase="fetching",
            branch_name=None,
        )
    cache.expire_on_read.add(activity_run_key(repository_id=repository.id, run_id="run-expired"))

    activity = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=repository.id
    )

    assert [edge["node"]["run_id"] for edge in activity["active_runs"]["edges"]] == ["run-kept"]


async def test_activity_answers_the_same_for_the_repository_name_as_for_its_id(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    repository: Node,
) -> None:
    service, cache = service_with_cache
    cache.storage[activity_run_key(repository_id=repository.id, run_id="run-a")] = activity_run_record(
        repository_id=repository.id,
        run_id="run-a",
        started_at="2026-09-08T10:00:00Z",
        phase="fetching",
        branch_name=None,
    )

    by_name = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=REPOSITORY_NAME
    )
    by_id = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=repository.id
    )

    assert by_name == by_id
    assert by_name["repository_id"] == repository.id
    assert [edge["node"]["run_id"] for edge in by_name["active_runs"]["edges"]] == ["run-a"]


async def test_activity_reports_the_holder_of_the_repository_lock(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    repository: Node,
) -> None:
    service, cache = service_with_cache
    cache.storage[f"lock.repository.{REPOSITORY_NAME}"] = "2026-09-08T10:30:00.000000Z::worker-9"

    activity = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=repository.id
    )

    assert activity["lock"] == {"worker_id": "worker-9", "requested_at": "2026-09-08T10:30:00+00:00"}
    assert activity["active_runs"] == {"edges": []}


async def test_activity_lists_one_last_run_per_operation_newest_first(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    service_with_cache: tuple[InfrahubServices, MemoryCache],
    repository: Node,
) -> None:
    service, cache = service_with_cache
    cache.storage[activity_last_run_key(repository_id=repository.id, operation="sync")] = last_run_record(
        operation="sync",
        finished_at="2026-09-08T10:00:00Z",
        branches=[(default_branch.name, "imported"), ("deleted-branch", "failed")],
    )
    cache.storage[activity_last_run_key(repository_id=repository.id, operation="add")] = last_run_record(
        operation="add", finished_at="2026-09-08T11:00:00Z", branches=[(default_branch.name, "failed")]
    )
    cache.storage[activity_last_run_key(repository_id=repository.id, operation="reimport")] = last_run_record(
        operation="reimport", finished_at="2026-09-08T09:30:00Z", branches=[]
    )

    activity = await query_activity(
        db=db, branch=default_branch, service=service, session=session_admin, repository_id=repository.id
    )

    assert activity["last_runs"] == {
        "edges": [
            {
                "node": {
                    "operation": "ADD",
                    "started_at": "2026-09-08T09:00:00+00:00",
                    "finished_at": "2026-09-08T11:00:00+00:00",
                    "branches": {"edges": [{"node": {"branch_name": default_branch.name, "outcome": "FAILED"}}]},
                }
            },
            {
                "node": {
                    "operation": "SYNC",
                    "started_at": "2026-09-08T09:00:00+00:00",
                    "finished_at": "2026-09-08T10:00:00+00:00",
                    "branches": {"edges": [{"node": {"branch_name": default_branch.name, "outcome": "IMPORTED"}}]},
                }
            },
            {
                "node": {
                    "operation": "REIMPORT",
                    "started_at": "2026-09-08T09:00:00+00:00",
                    "finished_at": "2026-09-08T09:30:00+00:00",
                    "branches": {"edges": []},
                }
            },
        ]
    }
