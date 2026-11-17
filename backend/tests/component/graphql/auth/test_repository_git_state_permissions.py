from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.git.state.cache_keys import activity_last_run_key, activity_run_key
from infrahub.services import InfrahubServices
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql_mutation, graphql_query
from tests.helpers.permissions import define_permissions
from tests.helpers.repository_git_state import RecordingRepositoryGitStateReader

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

IMPORTED_COMMIT = "1111111111111111111111111111111111111111"

COMMITS_QUERY = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id) {
    branch_name
    imported_commit
    condition
  }
}
"""

ACTIVITY_QUERY = """
query RepositoryActivity($id: String!) {
  InfrahubRepositoryActivity(id: $id) {
    active_runs { edges { node { run_id } } }
    last_runs { edges { node { branches { edges { node { branch_name outcome } } } } } }
  }
}
"""

UNKNOWN_ID = "18d39e83-1ef7-d650-5424-000000000000"

CHECK_REFS_MUTATION = """
mutation InfrahubReadOnlyRepositoryCheckRefs($id: String!) {
  InfrahubReadOnlyRepositoryCheckRefs(data: {id: $id}) {
    ok
    task { id }
  }
}
"""


@pytest.fixture
async def repository(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(db=db, name="permissioned-repo", location="/tmp/permissioned-repo", commit=IMPORTED_COMMIT)
    await repo.save(db=db)
    return repo


@pytest.fixture
async def read_only_repository(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    # Active because the check-refs mutation refuses any other internal status, which would
    # otherwise decide the outcome of the test that expects the permission to be granted.
    await repo.new(
        db=db,
        name="permissioned-read-only-repo",
        location="/tmp/permissioned-ro-repo",
        ref="main",
        commit=None,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )
    await repo.save(db=db)
    return repo


@pytest.fixture
async def tag(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> Node:
    node = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await node.new(db=db, name="not-a-repository")
    await node.save(db=db)
    return node


@pytest.fixture(autouse=True)
def recording_reader() -> Iterator[RecordingRepositoryGitStateReader]:
    """Answer from a double, so a permitted read never waits on a worker these tests do not run."""
    reader = RecordingRepositoryGitStateReader()
    original = config.OVERRIDE.repository_git_state_reader
    config.OVERRIDE.repository_git_state_reader = reader
    yield reader
    config.OVERRIDE.repository_git_state_reader = original


@pytest.fixture
async def service(db: InfrahubDatabase) -> InfrahubServices:
    # These tests are about who may reach the mutation, not about what it triggers.
    return await InfrahubServices.new(database=db, message_bus=BusRecorder(), workflow=WorkflowRecorder())


async def _account_session(db: InfrahubDatabase, name: str, permissions: list[ObjectPermission]) -> AccountSession:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, password="password123")
    await account.save(db=db)

    if permissions:
        await define_permissions(account=account, db=db, object_permissions=permissions)

    return AccountSession(authenticated=True, account_id=account.id, session_id=None, auth_type=AuthType.API)


async def test_repository_view_permission_reads_the_commit_log(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    repository: Node,
) -> None:
    session = await _account_session(
        db=db,
        name="repository-viewer",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    commits = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session,
    )

    assert not commits.errors
    assert commits.data
    assert commits.data["InfrahubRepositoryCommits"]["imported_commit"] == IMPORTED_COMMIT


async def test_missing_repository_view_permission_denies_the_commit_log(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    repository: Node,
) -> None:
    session = await _account_session(db=db, name="repository-outsider", permissions=[])

    commits = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session,
    )

    denial = "You do not have the following permission: object:Core:Repository:view:allow_default"
    assert commits.errors
    assert commits.errors[0].message == denial

    reloaded = await NodeManager.get_one(db=db, id=repository.id, branch=default_branch, raise_on_error=True)
    assert reloaded.commit.value == IMPORTED_COMMIT


async def test_missing_view_permission_denies_before_revealing_whether_an_id_exists(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    repository: Node,
) -> None:
    session = await _account_session(db=db, name="repository-prober", permissions=[])

    real_id = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session,
    )
    made_up_id = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": "18d39e83-1ef7-d650-5424-000000000000"},
        account_session=session,
    )

    denial = "You do not have the following permission: object:Core:Repository:view:allow_default"
    assert real_id.errors
    assert made_up_id.errors
    assert real_id.errors[0].message == denial
    assert made_up_id.errors[0].message == denial


async def test_repository_view_permission_still_reports_a_missing_id_as_missing(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    repository: Node,
) -> None:
    session = await _account_session(
        db=db,
        name="repository-viewer-missing-id",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    response = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": "18d39e83-1ef7-d650-5424-000000000000"},
        account_session=session,
    )

    assert response.errors
    assert (
        response.errors[0].message
        == "Unable to find the node 18d39e83-1ef7-d650-5424-000000000000 / CoreGenericRepository in the database."
    )


async def test_the_id_of_another_kind_is_reported_as_a_missing_repository(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    tag: Node,
) -> None:
    session = await _account_session(
        db=db,
        name="repository-viewer-other-kind",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    commits = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": tag.id},
        account_session=session,
    )

    assert commits.errors
    assert commits.errors[0].message == f"Unable to find the node {tag.id} / CoreGenericRepository in the database."


async def test_the_id_of_another_kind_denies_without_naming_that_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    tag: Node,
) -> None:
    session = await _account_session(db=db, name="repository-kind-prober", permissions=[])

    other_kind_id = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": tag.id},
        account_session=session,
    )
    made_up_id = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": "18d39e83-1ef7-d650-5424-000000000000"},
        account_session=session,
    )

    denial = "You do not have the following permission: object:Core:Repository:view:allow_default"
    assert other_kind_id.errors
    assert made_up_id.errors
    assert other_kind_id.errors[0].message == denial
    assert made_up_id.errors[0].message == denial


async def test_a_repository_kind_the_caller_cannot_view_is_reported_as_missing(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    read_only_repository: Node,
) -> None:
    session = await _account_session(
        db=db,
        name="read-write-repository-viewer",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    denied_kind = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": read_only_repository.id},
        account_session=session,
    )
    made_up_id = await graphql_query(
        query=COMMITS_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": "18d39e83-1ef7-d650-5424-000000000000"},
        account_session=session,
    )

    assert denied_kind.errors
    assert made_up_id.errors
    assert (
        denied_kind.errors[0].message
        == f"Unable to find the node {read_only_repository.id} / CoreGenericRepository in the database."
    )
    assert (
        made_up_id.errors[0].message
        == "Unable to find the node 18d39e83-1ef7-d650-5424-000000000000 / CoreGenericRepository in the database."
    )


async def test_activity_is_refused_with_the_answer_for_an_unknown_id(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    repository: Node,
    read_only_repository: Node,
) -> None:
    outsider = await _account_session(db=db, name="activity-outsider", permissions=[])
    read_write_viewer = await _account_session(
        db=db,
        name="activity-read-write-viewer",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    async def errors(session: AccountSession, repository_id: str) -> list[str]:
        response = await graphql_query(
            query=ACTIVITY_QUERY,
            db=db,
            branch=default_branch,
            service=service,
            variables={"id": repository_id},
            account_session=session,
        )
        assert response.data is None
        return [error.message for error in response.errors or []]

    denial = ["You do not have the following permission: object:Core:Repository:view:allow_default"]
    assert await errors(session=outsider, repository_id=repository.id) == denial
    assert await errors(session=outsider, repository_id=UNKNOWN_ID) == denial
    assert await errors(session=read_write_viewer, repository_id=read_only_repository.id) == [
        f"Unable to find the node {read_only_repository.id} / CoreGenericRepository in the database."
    ]
    assert await errors(session=read_write_viewer, repository_id=UNKNOWN_ID) == [
        f"Unable to find the node {UNKNOWN_ID} / CoreGenericRepository in the database."
    ]


@dataclass
class BranchVisibilityCase:
    name: str
    decision: PermissionDecision
    on_default_branch: bool
    """Whether the query runs on the default branch rather than on branch2."""
    run_ids: list[str]
    sees_default_branch: bool
    sees_branch2: bool


BRANCH_VISIBILITY_CASES: list[BranchVisibilityCase] = [
    BranchVisibilityCase(
        name="default_branch_only",
        decision=PermissionDecision.ALLOW_DEFAULT,
        on_default_branch=True,
        run_ids=["fetching", "on-default"],
        sees_default_branch=True,
        sees_branch2=False,
    ),
    BranchVisibilityCase(
        name="other_branches_only",
        decision=PermissionDecision.ALLOW_OTHER,
        on_default_branch=False,
        run_ids=["fetching", "on-branch2"],
        sees_default_branch=False,
        sees_branch2=True,
    ),
    BranchVisibilityCase(
        name="every_branch",
        decision=PermissionDecision.ALLOW_ALL,
        on_default_branch=True,
        run_ids=["fetching", "on-default", "on-branch2"],
        sees_default_branch=True,
        sees_branch2=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in BRANCH_VISIBILITY_CASES])
async def test_activity_leaves_out_the_branches_the_caller_cannot_view(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    repository: Node,
    case: BranchVisibilityCase,
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)
    cache = MemoryCache()
    service = await InfrahubServices.new(database=db, message_bus=BusRecorder(), cache=cache)
    for run_id, branch_name in (("fetching", None), ("on-default", default_branch.name), ("on-branch2", branch.name)):
        cache.storage[activity_run_key(repository_id=repository.id, run_id=run_id)] = json.dumps(
            {
                "run_id": run_id,
                "repository_id": repository.id,
                "operation": "sync",
                "phase": "fetching" if branch_name is None else "building",
                "branch_name": branch_name,
                "worker_id": "worker-1",
                "started_at": "2026-09-08T10:00:00Z",
                "updated_at": "2026-09-08T10:00:00Z",
            }
        )
    cache.storage[activity_last_run_key(repository_id=repository.id, operation="sync")] = json.dumps(
        {
            "operation": "sync",
            "started_at": "2026-09-08T09:00:00Z",
            "finished_at": "2026-09-08T09:01:00Z",
            "branches": [
                {"branch_name": default_branch.name, "outcome": "imported"},
                {"branch_name": branch.name, "outcome": "failed"},
            ],
        }
    )
    session = await _account_session(
        db=db,
        name=f"{case.name}-activity-viewer",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.VIEW.value,
                decision=case.decision.value,
            )
        ],
    )

    response = await graphql_query(
        query=ACTIVITY_QUERY,
        db=db,
        branch=default_branch if case.on_default_branch else branch,
        service=service,
        variables={"id": repository.id},
        account_session=session,
    )

    assert not response.errors
    assert response.data
    activity = response.data["InfrahubRepositoryActivity"]
    assert [edge["node"]["run_id"] for edge in activity["active_runs"]["edges"]] == case.run_ids
    expected_branches = []
    if case.sees_default_branch:
        expected_branches.append({"node": {"branch_name": default_branch.name, "outcome": "IMPORTED"}})
    if case.sees_branch2:
        expected_branches.append({"node": {"branch_name": branch.name, "outcome": "FAILED"}})
    assert activity["last_runs"]["edges"][0]["node"]["branches"] == {"edges": expected_branches}


async def test_check_refs_mutation_requires_update_permission(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    read_only_repository: Node,
) -> None:
    session = await _account_session(
        db=db,
        name="read-only-repository-viewer",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="ReadOnlyRepository",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    response = await graphql_mutation(
        query=CHECK_REFS_MUTATION,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": read_only_repository.id},
        account_session=session,
    )

    assert response.errors
    assert (
        response.errors[0].message
        == "You do not have the following permission: object:Core:ReadOnlyRepository:update:allow_default"
    )

    reloaded = await NodeManager.get_one(db=db, id=read_only_repository.id, branch=default_branch, raise_on_error=True)
    assert reloaded.commit.value is None


async def test_check_refs_mutation_accepts_update_permission(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    service: InfrahubServices,
    read_only_repository: Node,
) -> None:
    session = await _account_session(
        db=db,
        name="read-only-repository-editor",
        permissions=[
            ObjectPermission(
                namespace="Core",
                name="ReadOnlyRepository",
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )

    response = await graphql_mutation(
        query=CHECK_REFS_MUTATION,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": read_only_repository.id},
        account_session=session,
    )

    assert not response.errors
    assert response.data
    assert response.data["InfrahubReadOnlyRepositoryCheckRefs"]["ok"] is True
