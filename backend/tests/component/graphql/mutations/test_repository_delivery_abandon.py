from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.constants import (
    GlobalPermissions,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
    RepositoryInternalStatus,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreRepository
from infrahub.git.models import GitRepositoryDeliveryAbandon
from infrahub.git.writeback.models import DeliveryQueue, PendingMerge
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.lock import InfrahubLockRegistry
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import GIT_REPOSITORY_DELIVERY_ABANDON
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql_mutation
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

REPOSITORY_NAME = "delivery-repository"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"

ABANDON = """
mutation Abandon($id: String!, $queue_version: Int!) {
    InfrahubRepositoryDeliveryAbandon(data: {id: $id, queue_version: $queue_version}) {
        ok
        task {
            id
        }
    }
}
"""

UPDATE_REPOSITORY = ObjectPermission(
    namespace="Core",
    name="Repository",
    action=PermissionAction.UPDATE.value,
    decision=PermissionDecision.ALLOW_DEFAULT.value,
)
MANAGE_REPOSITORIES = GlobalPermission(
    action=GlobalPermissions.MANAGE_REPOSITORIES.value, decision=PermissionDecision.ALLOW_ALL.value
)
EDIT_DEFAULT_BRANCH = GlobalPermission(
    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
)


@dataclass
class AbandonUnderTest:
    db: InfrahubDatabase
    account: Node
    session: AccountSession
    store: WritebackIntentStore
    workflow: WorkflowRecorder
    service: InfrahubServices
    repository_id: str

    async def grant(
        self,
        object_permissions: list[ObjectPermission] | None = None,
        global_permissions: list[GlobalPermission] | None = None,
    ) -> None:
        await define_permissions(
            account=self.account,
            db=self.db,
            object_permissions=object_permissions,
            global_permissions=global_permissions,
        )

    async def grant_all(self) -> None:
        await self.grant(
            object_permissions=[UPDATE_REPOSITORY], global_permissions=[MANAGE_REPOSITORIES, EDIT_DEFAULT_BRANCH]
        )

    async def enqueue(self, entry_id: str) -> None:
        await self.store.enqueue(
            repository_id=self.repository_id,
            entry=PendingMerge(
                entry_id=entry_id,
                source_branch="feature-1",
                source_git_branch="feature-1",
                source_commit=SOURCE_COMMIT,
                merged_at=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
            ),
            widen=False,
        )

    async def queue(self) -> DeliveryQueue:
        return (await self.store.read(repository_id=self.repository_id)).queue

    async def abandon(
        self, queue_version: int, repository_id: str | None = None, branch: Branch | None = None
    ) -> ExecutionResult:
        return await graphql_mutation(
            query=ABANDON,
            db=self.db,
            service=self.service,
            branch=branch,
            variables={"id": repository_id or self.repository_id, "queue_version": queue_version},
            account_session=self.session,
        )


@pytest.fixture
async def subject(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> AbandonUnderTest:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repository.new(db=db, name=REPOSITORY_NAME, location=f"https://git.example.com/{REPOSITORY_NAME}.git")
    await repository.save(db=db)
    workflow = WorkflowRecorder()
    return AbandonUnderTest(
        db=db,
        account=first_account,
        session=session_first_account,
        store=WritebackIntentStore(
            db=db,
            lock_registry=InfrahubLockRegistry(local_only=True),
            default_branch=default_branch,
            clock=lambda: datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
        ),
        workflow=workflow,
        service=await InfrahubServices.new(database=db, workflow=workflow),
        repository_id=repository.id,
    )


def error_messages(result: ExecutionResult) -> list[str]:
    return [error.message for error in result.errors or []]


async def test_submits_the_abandonment_of_the_queue_version(subject: AbandonUnderTest) -> None:
    await subject.grant_all()
    await subject.enqueue(entry_id="merge-1")
    queue_before = await subject.queue()

    result = await subject.abandon(queue_version=1)

    assert result.errors is None
    assert result.data
    payload = result.data["InfrahubRepositoryDeliveryAbandon"]
    assert payload["ok"] is True
    UUID(payload["task"]["id"])
    assert subject.workflow.submit_calls == [
        {
            "kind": "submit",
            "workflow": GIT_REPOSITORY_DELIVERY_ABANDON,
            "parameters": {
                "model": GitRepositoryDeliveryAbandon(
                    repository_id=subject.repository_id, repository_name=REPOSITORY_NAME, queue_version=1
                )
            },
            "tags": [],
        }
    ]
    # The workflow removes the entries, so the request alone leaves the queue as it was.
    assert await subject.queue() == queue_before


async def test_refuses_a_request_off_the_default_branch(subject: AbandonUnderTest) -> None:
    await subject.grant_all()
    await subject.enqueue(entry_id="merge-1")
    queue_before = await subject.queue()
    feature = await create_branch(branch_name="feature", db=subject.db)

    result = await subject.abandon(queue_version=1, branch=feature)

    assert error_messages(result) == ["Send this request on the default branch main; the pending pushes live there."]
    assert subject.workflow.submit_calls == []
    assert await subject.queue() == queue_before


@dataclass
class MissingPermissionCase:
    name: str
    object_permissions: list[ObjectPermission]
    global_permissions: list[GlobalPermission]
    message: str


MISSING_PERMISSION_CASES: list[MissingPermissionCase] = [
    MissingPermissionCase(
        name="update_on_repository",
        object_permissions=[],
        global_permissions=[MANAGE_REPOSITORIES, EDIT_DEFAULT_BRANCH],
        message="You do not have the following permission: object:Core:Repository:update:allow_default",
    ),
    MissingPermissionCase(
        name="manage_repositories",
        object_permissions=[UPDATE_REPOSITORY],
        global_permissions=[EDIT_DEFAULT_BRANCH],
        message="You are not allowed to manage repositories",
    ),
    MissingPermissionCase(
        name="edit_default_branch",
        object_permissions=[UPDATE_REPOSITORY],
        global_permissions=[MANAGE_REPOSITORIES],
        message="You are not allowed to change data in the default branch",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in MISSING_PERMISSION_CASES])
async def test_refuses_an_account_without_each_permission(
    subject: AbandonUnderTest, test_case: MissingPermissionCase
) -> None:
    await subject.grant(
        object_permissions=test_case.object_permissions, global_permissions=test_case.global_permissions
    )
    await subject.enqueue(entry_id="merge-1")
    queue_before = await subject.queue()

    result = await subject.abandon(queue_version=1)

    assert error_messages(result) == [test_case.message]
    assert subject.workflow.submit_calls == []
    assert await subject.queue() == queue_before


async def test_refuses_a_queue_version_that_moved(subject: AbandonUnderTest) -> None:
    await subject.grant_all()
    await subject.enqueue(entry_id="merge-1")
    await subject.enqueue(entry_id="merge-2")
    queue_before = await subject.queue()
    assert queue_before.version == 2

    result = await subject.abandon(queue_version=1)

    assert error_messages(result) == [
        f"The pending pushes of repository {REPOSITORY_NAME} changed since version 1; reload and try again."
    ]
    assert subject.workflow.submit_calls == []
    assert await subject.queue() == queue_before


async def test_refuses_an_empty_queue(subject: AbandonUnderTest) -> None:
    await subject.grant_all()
    queue_before = await subject.queue()
    assert queue_before == DeliveryQueue(version=0, entries=())

    result = await subject.abandon(queue_version=0)

    assert error_messages(result) == [f"Repository {REPOSITORY_NAME} has nothing pending to push."]
    assert subject.workflow.submit_calls == []


async def test_refuses_a_read_only_repository(subject: AbandonUnderTest, default_branch: Branch) -> None:
    await subject.grant_all()
    read_only = await Node.init(db=subject.db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await read_only.new(
        db=subject.db, name="read-only-repository", location="/tmp/read-only", ref="main", commit=SOURCE_COMMIT
    )
    await read_only.save(db=subject.db)

    result = await subject.abandon(queue_version=0, repository_id=read_only.id)

    assert error_messages(result) == ["Repository read-only-repository is read-only and never pushes to its remote."]
    assert subject.workflow.submit_calls == []


async def test_refuses_a_staging_repository(subject: AbandonUnderTest, default_branch: Branch) -> None:
    await subject.grant_all()
    await subject.enqueue(entry_id="merge-1")
    queue_before = await subject.queue()
    repository = await NodeManager.get_one(
        db=subject.db, id=subject.repository_id, kind=CoreRepository, branch=default_branch, raise_on_error=True
    )
    repository.internal_status.value = RepositoryInternalStatus.STAGING.value
    await repository.save(db=subject.db)

    result = await subject.abandon(queue_version=1)

    assert error_messages(result) == [
        f"Repository {REPOSITORY_NAME} is staging; its changes are pushed when its proposed change merges."
    ]
    assert subject.workflow.submit_calls == []
    assert await subject.queue() == queue_before
