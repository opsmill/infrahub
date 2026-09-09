from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_mutation, graphql_query
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
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

DRIFT_QUERY = """
query RepositoryBranchDrift($id: String!) {
  InfrahubRepositoryBranchDrift(repository_id: $id) {
    repository_id
    unavailable { reason }
  }
}
"""

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
    await repo.new(
        db=db, name="permissioned-read-only-repo", location="/tmp/permissioned-ro-repo", ref="main", commit=None
    )
    await repo.save(db=db)
    return repo


@pytest.fixture
async def service(db: InfrahubDatabase) -> InfrahubServices:
    return await InfrahubServices.new(database=db, message_bus=BusRecorder(), workflow=WorkflowLocalExecution())


async def _account_session(db: InfrahubDatabase, name: str, permissions: list[ObjectPermission]) -> AccountSession:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, password="password123")
    await account.save(db=db)

    if permissions:
        await define_permissions(account=account, db=db, object_permissions=permissions)

    return AccountSession(authenticated=True, account_id=account.id, session_id=None, auth_type=AuthType.API)


async def test_repository_view_permission_reads_both_queries(
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
    drift = await graphql_query(
        query=DRIFT_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session,
    )

    assert not commits.errors
    assert commits.data
    assert commits.data["InfrahubRepositoryCommits"]["imported_commit"] == IMPORTED_COMMIT
    assert not drift.errors
    assert drift.data
    assert drift.data["InfrahubRepositoryBranchDrift"]["repository_id"] == repository.id


async def test_missing_repository_view_permission_denies_both_queries(
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
    drift = await graphql_query(
        query=DRIFT_QUERY,
        db=db,
        branch=default_branch,
        service=service,
        variables={"id": repository.id},
        account_session=session,
    )

    denial = "You do not have the following permission: object:Core:Repository:view:allow_default"
    assert commits.errors
    assert commits.errors[0].message == denial
    assert drift.errors
    assert drift.errors[0].message == denial

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
