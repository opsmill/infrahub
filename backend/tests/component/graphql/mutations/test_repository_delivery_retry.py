from __future__ import annotations

import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.constants import (
    GlobalPermissions,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
    RepositoryInternalStatus,
)
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.git.models import GitRepositoryDeliveryRetry
from infrahub.git.writeback.models import DeliveryFailure, PendingMerge
from infrahub.git.writeback.service import REPOSITORY_LOCK_NAMESPACE
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import GIT_REPOSITORY_DELIVERY_RETRY
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql_mutation
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import WritebackIntent

REPOSITORY_NAME = "delivery-repository"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"

RETRY_DELIVERY = """
mutation RetryDelivery($id: String!) {
    InfrahubRepositoryDeliveryRetry(data: {id: $id}) {
        ok
        task {
            id
        }
    }
}
"""

REPOSITORY_UPDATE = ObjectPermission(
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


class RepositorySetup(StrEnum):
    PENDING = "pending"
    EMPTY_QUEUE = "empty-queue"
    STAGING_PENDING = "staging-pending"
    READ_ONLY = "read-only"


def build_store(db: InfrahubDatabase, default_branch: Branch, now: datetime) -> WritebackIntentStore:
    return WritebackIntentStore(db=db, lock_registry=lock.registry, default_branch=default_branch, clock=lambda: now)


async def create_repository(
    db: InfrahubDatabase, store: WritebackIntentStore, default_branch: Branch, setup: RepositorySetup
) -> Node:
    if setup == RepositorySetup.READ_ONLY:
        repository = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
        await repository.new(
            db=db,
            name=REPOSITORY_NAME,
            location=f"https://git.example.com/{REPOSITORY_NAME}.git",
            ref="main",
            commit=SOURCE_COMMIT,
        )
        await repository.save(db=db)
        return repository

    internal_status = (
        RepositoryInternalStatus.STAGING
        if setup == RepositorySetup.STAGING_PENDING
        else RepositoryInternalStatus.ACTIVE
    )
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repository.new(
        db=db,
        name=REPOSITORY_NAME,
        location=f"https://git.example.com/{REPOSITORY_NAME}.git",
        internal_status=internal_status.value,
    )
    await repository.save(db=db)
    if setup != RepositorySetup.EMPTY_QUEUE:
        await store.enqueue(repository_id=repository.id, entry=pending_merge(merged_at=store.clock()), widen=False)
    return repository


def pending_merge(merged_at: datetime) -> PendingMerge:
    return PendingMerge(
        entry_id=str(uuid.uuid4()),
        source_branch="feature-1",
        source_git_branch="feature-1",
        source_commit=SOURCE_COMMIT,
        merged_at=merged_at,
    )


async def read_delivery_state(store: WritebackIntentStore, repository: Node) -> WritebackIntent | None:
    # A read-only repository has no delivery state to compare.
    if repository.get_kind() != InfrahubKind.REPOSITORY:
        return None
    return await store.read(repository_id=repository.id)


@dataclass
class RefusalCase:
    name: str
    expected_error: str
    object_permissions: list[ObjectPermission] = field(default_factory=lambda: [REPOSITORY_UPDATE])
    global_permissions: list[GlobalPermission] = field(
        default_factory=lambda: [MANAGE_REPOSITORIES, EDIT_DEFAULT_BRANCH]
    )
    on_other_branch: bool = False
    repository: RepositorySetup = RepositorySetup.PENDING


REFUSAL_CASES: list[RefusalCase] = [
    RefusalCase(
        name="sent_on_another_branch",
        on_other_branch=True,
        expected_error="Send this request on the default branch main; the pending pushes live there.",
    ),
    RefusalCase(
        name="without_repository_update",
        object_permissions=[],
        expected_error="You do not have the following permission: object:Core:Repository:update:allow_default",
    ),
    RefusalCase(
        name="with_repository_update_on_other_branches_only",
        object_permissions=[
            ObjectPermission(
                namespace="Core",
                name="Repository",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_OTHER.value,
            )
        ],
        expected_error="You do not have the following permission: object:Core:Repository:update:allow_default",
    ),
    RefusalCase(
        name="without_manage_repositories",
        global_permissions=[EDIT_DEFAULT_BRANCH],
        expected_error="You are not allowed to manage repositories",
    ),
    RefusalCase(
        name="without_edit_default_branch",
        global_permissions=[MANAGE_REPOSITORIES],
        expected_error="You are not allowed to change data in the default branch",
    ),
    RefusalCase(
        name="nothing_pending",
        repository=RepositorySetup.EMPTY_QUEUE,
        expected_error=f"Repository {REPOSITORY_NAME} has nothing pending to push.",
    ),
    RefusalCase(
        name="read_only_repository",
        repository=RepositorySetup.READ_ONLY,
        expected_error=f"Repository {REPOSITORY_NAME} is read-only and never pushes to its remote.",
    ),
    RefusalCase(
        name="staging_repository",
        repository=RepositorySetup.STAGING_PENDING,
        expected_error=(
            f"Repository {REPOSITORY_NAME} is staging; its changes are pushed when its proposed change merges."
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REFUSAL_CASES])
async def test_retry_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
    test_case: RefusalCase,
) -> None:
    store = build_store(db=db, default_branch=default_branch, now=datetime.now(UTC))
    repository = await create_repository(db=db, store=store, default_branch=default_branch, setup=test_case.repository)
    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=test_case.object_permissions,
        global_permissions=test_case.global_permissions,
    )
    request_branch = await create_branch(branch_name="feature", db=db) if test_case.on_other_branch else default_branch
    before = await read_delivery_state(store=store, repository=repository)
    recorder = WorkflowRecorder()

    result = await graphql_mutation(
        query=RETRY_DELIVERY,
        db=db,
        branch=request_branch,
        variables={"id": repository.id},
        service=await InfrahubServices.new(database=db, message_bus=BusRecorder(), workflow=recorder),
        account_session=session_first_account,
    )

    assert result.errors
    assert [error.message for error in result.errors] == [test_case.expected_error]
    assert recorder.submit_calls == []
    assert await read_delivery_state(store=store, repository=repository) == before


async def start_attempt(store: WritebackIntentStore, repository_id: str, now: datetime) -> None:
    await store.start_attempt(repository_id=repository_id)


async def fail_with_retry_due(store: WritebackIntentStore, repository_id: str, now: datetime) -> None:
    await store.start_attempt(repository_id=repository_id)
    await store.record_failure(
        repository_id=repository_id,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message="Connection refused"
        ),
        final=False,
        retry_due_at=now + timedelta(minutes=5),
    )


async def leave_as_queued(store: WritebackIntentStore, repository_id: str, now: datetime) -> None:
    return


async def fail_on_policy(store: WritebackIntentStore, repository_id: str, now: datetime) -> None:
    await store.start_attempt(repository_id=repository_id)
    await store.record_failure(
        repository_id=repository_id,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CREDENTIALS, retryable=False, message="Authentication failed"
        ),
        final=True,
        retry_due_at=None,
    )


@dataclass
class AllowedCase:
    name: str
    seed: Callable[[WritebackIntentStore, str, datetime], Awaitable[None]]
    expected_status: RepositoryDeliveryStatus
    progress_age: timedelta = timedelta(0)
    """How long before the request the state was last written."""
    retry_due: bool = False
    hold_repository_lock: bool = False


ALLOWED_CASES: list[AllowedCase] = [
    AllowedCase(
        name="attempt_running",
        seed=start_attempt,
        expected_status=RepositoryDeliveryStatus.PENDING,
        hold_repository_lock=True,
    ),
    AllowedCase(
        name="automatic_retry_waiting",
        seed=fail_with_retry_due,
        expected_status=RepositoryDeliveryStatus.PENDING,
        retry_due=True,
    ),
    AllowedCase(
        name="stale_pending",
        seed=leave_as_queued,
        expected_status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(hours=1),
    ),
    AllowedCase(
        name="action_required",
        seed=fail_on_policy,
        expected_status=RepositoryDeliveryStatus.ACTION_REQUIRED,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ALLOWED_CASES])
async def test_retry_submits_the_delivery_flow(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
    test_case: AllowedCase,
) -> None:
    written_at = datetime.now(UTC) - test_case.progress_age
    store = build_store(db=db, default_branch=default_branch, now=written_at)
    repository = await create_repository(
        db=db, store=store, default_branch=default_branch, setup=RepositorySetup.PENDING
    )
    await test_case.seed(store, repository.id, written_at)
    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[REPOSITORY_UPDATE],
        global_permissions=[MANAGE_REPOSITORIES, EDIT_DEFAULT_BRANCH],
    )
    intent = await store.read(repository_id=repository.id)
    assert intent.status == test_case.expected_status
    assert len(intent.queue.entries) == 1
    assert intent.progress.last_progress_at == written_at
    assert (intent.progress.retry_due_at is not None) == test_case.retry_due
    recorder = WorkflowRecorder()

    async with AsyncExitStack() as stack:
        if test_case.hold_repository_lock:
            await stack.enter_async_context(
                lock.registry.get(name=REPOSITORY_NAME, namespace=REPOSITORY_LOCK_NAMESPACE)
            )
        result = await graphql_mutation(
            query=RETRY_DELIVERY,
            db=db,
            variables={"id": repository.id},
            service=await InfrahubServices.new(database=db, message_bus=BusRecorder(), workflow=recorder),
            account_session=session_first_account,
        )

    assert not result.errors
    assert result.data
    response = result.data["InfrahubRepositoryDeliveryRetry"]
    assert response["ok"] is True
    assert uuid.UUID(response["task"]["id"])
    assert recorder.submit_calls == [
        {
            "kind": "submit",
            "workflow": GIT_REPOSITORY_DELIVERY_RETRY,
            "parameters": {
                "model": GitRepositoryDeliveryRetry(
                    repository_id=repository.id, repository_name=REPOSITORY_NAME, manual=True
                )
            },
            "tags": [f"infrahub.app/node/{repository.id}", "infrahub.app/repository-delivery"],
        }
    ]
