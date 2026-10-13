from __future__ import annotations

import asyncio
import logging
import math
from contextlib import asynccontextmanager, contextmanager, nullcontext
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, override
from uuid import uuid4

import pytest
from prefect import flow
from structlog.testing import capture_logs

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import (
    FullRegenerationReason,
    InfrahubKind,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
    RepositoryInternalStatus,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.repository_merge_dispatcher import RepositoryMergeDispatcher
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.exceptions import DeliveryStateUnavailableError
from infrahub.git import tasks as git_tasks
from infrahub.git.models import GitRepositoryDeliveryRetry, GitRepositoryMerge
from infrahub.git.tasks import git_branch_delete, merge_git_repository, retry_repository_delivery
from infrahub.git.writeback.constants import STATE_LOCK_ACQUIRE_SECONDS, STATE_LOCK_TTL_SECONDS
from infrahub.git.writeback.models import DeliveryFailure, DeliveryQueue, HeldRegeneration, HeldWiden, PendingMerge
from infrahub.git.writeback.service import REPOSITORY_LOCK_NAMESPACE
from infrahub.git.writeback.store import STATE_LOCK_NAMESPACE, WritebackIntentStore
from infrahub.message_bus.messages.refresh_git_repository_branch_deleted import RefreshGitRepositoryBranchDeleted
from infrahub.workers.dependencies import build_client, build_message_bus
from infrahub.workflows.catalogue import GIT_REPOSITORIES_MERGE
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.git import LocalRemote, build_repository_client, clone_repository
from tests.helpers.workflow_override import override_workflow

from .conftest import HELD_REGENERATION, QUEUE, SOURCE_COMMIT, pending_merge, read_attribute_writes

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from prefect.client.schemas.objects import State

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.git.repository import InfrahubRepository
    from infrahub.git.writeback.models import WritebackIntent
    from infrahub.lock import InfrahubLock
    from tests.adapters.lock.timeline import LockTimeline

REPOSITORY_NAME = "delivery-repository"
SOURCE_BRANCH = "feature-1"
TRUNK_COMMIT = "a" * 40
MOVED_TRUNK_COMMIT = "c" * 40
DISPATCHER_LOGGER = "tests.repository_merge_dispatcher"
RUN_LOGGER = "infrahub.tasks"
FLOW_LOGGER = "prefect.flow_runs"
TASK_LOGGER = "prefect.task_runs"


class RecordingSleep:
    """Records each delay and returns at once."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class SleepUntilEveryRepositoryWaits:
    """Holds each delay until the given number of repositories wait at the same time, then returns."""

    def __init__(self, *, repositories: int) -> None:
        self.delays: list[float] = []
        self.repositories = repositories
        self.every_repository_waits = asyncio.Event()

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
        if len(self.delays) == self.repositories:
            self.every_repository_waits.set()
        # Repositories queued one after the other never wait together, so the bound ends the dispatch.
        await asyncio.wait_for(self.every_repository_waits.wait(), timeout=10)


def state_lock_not_acquired(repository_id: str) -> Exception:
    return DeliveryStateUnavailableError(repository_id=repository_id, acquire_seconds=STATE_LOCK_ACQUIRE_SECONDS)


class FailingEnqueueStore(WritebackIntentStore):
    """A store whose first tries to queue a merge of a repository raise the error that `error` makes for it."""

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        default_branch: Branch,
        failing_tries: dict[str, float],
        error: Callable[[str], Exception] = state_lock_not_acquired,
    ) -> None:
        super().__init__(
            db=db, lock_registry=lock.registry, default_branch=default_branch, clock=partial(datetime.now, UTC)
        )
        self.failing_tries = failing_tries
        self.error = error

    @override
    async def enqueue(self, *, repository_id: str, entry: PendingMerge, widen: bool) -> WritebackIntent:
        if self.failing_tries.get(repository_id, 0) > 0:
            self.failing_tries[repository_id] -= 1
            raise self.error(repository_id)
        return await super().enqueue(repository_id=repository_id, entry=entry, widen=widen)


@dataclass
class ClonedRepository:
    """A repository whose remote is on disk, with its clone on this worker."""

    id: str
    remote: LocalRemote
    clone: InfrahubRepository
    client: InfrahubClient
    trunk_commit: str
    default_branch: Branch
    source_branch: Branch

    def merge_model(self, *, entry: PendingMerge | None, enqueued: bool) -> GitRepositoryMerge:
        return GitRepositoryMerge(
            repository_id=self.id,
            repository_name=REPOSITORY_NAME,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_branch=SOURCE_BRANCH,
            destination_branch=self.default_branch.name,
            destination_branch_id=str(self.default_branch.get_uuid()),
            repository_kind=InfrahubKind.REPOSITORY,
            pending_merge=entry,
            pending_merge_enqueued=enqueued,
        )

    def remove_origin(self) -> None:
        git_repo = self.clone.get_git_repo_main()
        git_repo.delete_remote(git_repo.remote("origin"))


async def create_repository_node(
    db: InfrahubDatabase,
    branch: Branch,
    name: str,
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
    commit: str = TRUNK_COMMIT,
    location: str | None = None,
) -> Node:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=branch)
    await repository.new(
        db=db,
        name=name,
        location=location or f"https://git.example.com/{name}.git",
        internal_status=internal_status.value,
        commit=commit,
    )
    await repository.save(db=db)
    return repository


async def fork_source_branch(db: InfrahubDatabase) -> Branch:
    """Create the branch that merges, after the repositories, so it holds them."""
    branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
    branch.sync_with_git = True
    await branch.save(db=db)
    return branch


async def set_values(db: InfrahubDatabase, branch: Branch, repository_id: str, **values: str) -> None:
    repository = await NodeManager.get_one(
        db=db, id=repository_id, kind=InfrahubKind.REPOSITORY, branch=branch, raise_on_error=True
    )
    for name, value in values.items():
        repository.get_attribute(name=name).value = value
    await repository.save(db=db)


def build_store(db: InfrahubDatabase, default_branch: Branch) -> WritebackIntentStore:
    return WritebackIntentStore(
        db=db, lock_registry=lock.registry, default_branch=default_branch, clock=partial(datetime.now, UTC)
    )


async def dispatch_merge(
    db: InfrahubDatabase,
    source_branch: Branch,
    default_branch: Branch,
    sleep: Callable[[float], Awaitable[None]],
    failing_tries: dict[str, float] | None = None,
    error: Callable[[str], Exception] = state_lock_not_acquired,
) -> WorkflowRecorder:
    """Run the repository part of a branch merge, where the first tries of each repository in `failing_tries` fail."""
    workflow = WorkflowRecorder()
    # Every session of the dispatch counts down the same tries.
    tries = failing_tries if failing_tries is not None else {}
    dispatcher = RepositoryMergeDispatcher(
        db=db,
        source_branch=source_branch,
        destination_branch=default_branch,
        workflow=workflow,
        state_for_session=lambda session: FailingEnqueueStore(
            db=session, default_branch=default_branch, failing_tries=tries, error=error
        ),
        sleep=sleep,
        logger=logging.getLogger(DISPATCHER_LOGGER),
    )
    await dispatcher.merge_repositories(
        context=InfrahubContext.init(
            branch=default_branch, account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE)
        )
    )
    return workflow


def submitted_merges(workflow: WorkflowRecorder) -> list[GitRepositoryMerge]:
    return [call["parameters"]["model"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_MERGE)]


def log_lines(caplog: pytest.LogCaptureFixture, logger_name: str, level: int) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == logger_name and record.levelno == level]


async def run_merge_flow(dependency_provider: Provider, client: InfrahubClient, model: GitRepositoryMerge) -> State:
    bus = BusRecorder()
    with (
        override_dependency(build_client, lambda: client, dependency_provider=dependency_provider),
        override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider),
    ):
        return await merge_git_repository(model=model, return_state=True)


async def run_retry_flow(dependency_provider: Provider, client: InfrahubClient, repository_id: str) -> State:
    bus = BusRecorder()
    with (
        override_dependency(build_client, lambda: client, dependency_provider=dependency_provider),
        override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider),
    ):
        return await retry_repository_delivery(
            model=GitRepositoryDeliveryRetry(repository_id=repository_id, repository_name=REPOSITORY_NAME),
            context=InfrahubContext(
                branch=BranchContext(name=registry.default_branch),
                account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
            ),
            return_state=True,
        )


@asynccontextmanager
async def held_lock(held: InfrahubLock) -> AsyncIterator[asyncio.Event]:
    """Keep the lock taken by another worker until the block ends or the yielded event is set."""
    taken = asyncio.Event()
    released = asyncio.Event()

    async def hold() -> None:
        async with held:
            taken.set()
            await released.wait()

    # The lock lets the task that owns it in again, so only a lock taken in another task blocks the flow.
    holder = asyncio.create_task(hold())
    await taken.wait()
    try:
        yield released
    finally:
        released.set()
        await holder


class SetEventOnMessage(logging.Handler):
    def __init__(self, *, event: asyncio.Event, message: str) -> None:
        super().__init__()
        self.event = event
        self.message = message

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == self.message:
            self.event.set()


@contextmanager
def set_on_log(event: asyncio.Event, logger_name: str, message: str) -> Iterator[None]:
    """Set the event when the logger logs the message."""
    handler = SetEventOnMessage(event=event, message=message)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def immediate_delivery_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the retries of the delivery task with no wait, so a failing attempt does not sleep through the real delays."""
    monkeypatch.setattr(
        git_tasks, "deliver_pending_merges", git_tasks.deliver_pending_merges.with_options(retry_delay_seconds=0)
    )


@pytest.fixture
async def cloned_repository(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    tmp_path: Path,
    git_repos_dir: Path,
) -> ClonedRepository:
    # The remote checks out another branch, so it accepts a push to its trunk.
    remote = LocalRemote.create(directory=tmp_path / "remote", trunk="main", branches=["parking"], head="parking")
    trunk_commit = remote.repo.commit("main").hexsha
    node = await create_repository_node(
        db=db, branch=default_branch, name=REPOSITORY_NAME, commit=trunk_commit, location=str(remote.directory)
    )
    client = build_repository_client(
        repository_id=node.id,
        name=REPOSITORY_NAME,
        location=str(remote.directory),
        default_branch="main",
        commit=trunk_commit,
    )
    clone = await clone_repository(
        id=node.id, name=REPOSITORY_NAME, location=str(remote.directory), client=client, update_commit_value=False
    )
    return ClonedRepository(
        id=node.id,
        remote=remote,
        clone=clone,
        client=client,
        trunk_commit=trunk_commit,
        default_branch=default_branch,
        source_branch=await fork_source_branch(db=db),
    )


@dataclass
class NoContentCase:
    name: str
    branch_commit: str | None
    """The commit that the branch records, or None when it records none of its own."""
    trunk_commit_now: str


NO_CONTENT_CASES = [
    NoContentCase(
        name="data_only_branch_forked_before_the_trunk_moved", branch_commit=None, trunk_commit_now=MOVED_TRUNK_COMMIT
    ),
    NoContentCase(
        name="branch_holds_the_commit_that_the_trunk_holds_now",
        branch_commit=MOVED_TRUNK_COMMIT,
        trunk_commit_now=MOVED_TRUNK_COMMIT,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in NO_CONTENT_CASES])
async def test_a_merge_with_no_content_queues_nothing_and_submits_no_merge_workflow(
    case: NoContentCase, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    repository = await create_repository_node(db=db, branch=default_branch, name=REPOSITORY_NAME)
    source_branch = await fork_source_branch(db=db)
    if case.branch_commit is not None:
        await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=case.branch_commit)
    await set_values(db=db, branch=default_branch, repository_id=repository.id, commit=case.trunk_commit_now)
    store = build_store(db=db, default_branch=default_branch)

    workflow = await dispatch_merge(
        db=db, source_branch=source_branch, default_branch=default_branch, sleep=RecordingSleep()
    )

    assert workflow.submit_calls == []
    assert (await store.read(repository_id=repository.id)).queue == DeliveryQueue()


async def test_a_staging_repository_merges_with_no_queue_entry(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    repository = await create_repository_node(
        db=db, branch=default_branch, name=REPOSITORY_NAME, internal_status=RepositoryInternalStatus.INACTIVE
    )
    source_branch = await fork_source_branch(db=db)
    await set_values(
        db=db,
        branch=source_branch,
        repository_id=repository.id,
        internal_status=RepositoryInternalStatus.STAGING.value,
        commit=SOURCE_COMMIT,
    )
    store = build_store(db=db, default_branch=default_branch)

    workflow = await dispatch_merge(
        db=db, source_branch=source_branch, default_branch=default_branch, sleep=RecordingSleep()
    )

    assert submitted_merges(workflow) == [
        GitRepositoryMerge(
            repository_id=repository.id,
            repository_name=REPOSITORY_NAME,
            internal_status=RepositoryInternalStatus.STAGING.value,
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
            destination_branch_id=str(default_branch.get_uuid()),
            repository_kind=InfrahubKind.REPOSITORY,
            source_commit=SOURCE_COMMIT,
        )
    ]
    assert (await store.read(repository_id=repository.id)).queue == DeliveryQueue()


async def test_a_merge_is_queued_behind_a_delivery_that_waits_for_an_action_and_its_merge_flow_is_submitted(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    repository = await create_repository_node(db=db, branch=default_branch, name=REPOSITORY_NAME)
    source_branch = await fork_source_branch(db=db)
    await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)
    store = build_store(db=db, default_branch=default_branch)
    earlier = pending_merge(entry_id=str(uuid4()), source_git_branch="earlier-feature")
    await store.enqueue(repository_id=repository.id, entry=earlier, widen=False)
    await store.record_failure(
        repository_id=repository.id,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.PERMISSION, retryable=False, message="remote: Permission denied"
        ),
        final=True,
        retry_due_at=None,
    )
    sleep = RecordingSleep()

    workflow = await dispatch_merge(db=db, source_branch=source_branch, default_branch=default_branch, sleep=sleep)

    (model,) = submitted_merges(workflow)
    entry = model.pending_merge
    assert entry is not None
    assert model == GitRepositoryMerge(
        repository_id=repository.id,
        repository_name=REPOSITORY_NAME,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        source_branch=SOURCE_BRANCH,
        destination_branch=default_branch.name,
        destination_branch_id=str(default_branch.get_uuid()),
        repository_kind=InfrahubKind.REPOSITORY,
        source_commit=SOURCE_COMMIT,
        pending_merge=entry,
        pending_merge_enqueued=True,
    )
    assert (entry.source_branch, entry.source_git_branch, entry.source_commit, entry.delete_source_git_branch) == (
        SOURCE_BRANCH,
        SOURCE_BRANCH,
        SOURCE_COMMIT,
        False,
    )
    assert sleep.delays == []
    assert (await store.read(repository_id=repository.id)).queue.entries == (earlier, entry)


async def test_a_failed_enqueue_of_one_repository_still_submits_the_merge_of_the_others(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    failing = await create_repository_node(db=db, branch=default_branch, name="failing-repository")
    healthy = await create_repository_node(db=db, branch=default_branch, name="healthy-repository")
    source_branch = await fork_source_branch(db=db)
    for repository in (failing, healthy):
        await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)

    workflow = await dispatch_merge(
        db=db,
        source_branch=source_branch,
        default_branch=default_branch,
        failing_tries={failing.id: math.inf},
        error=lambda repository_id: RuntimeError(f"The cache of the state lock of {repository_id} does not answer."),
        sleep=RecordingSleep(),
    )

    merges = {model.repository_name: model for model in submitted_merges(workflow)}
    assert {name: model.pending_merge_enqueued for name, model in merges.items()} == {
        "failing-repository": False,
        "healthy-repository": True,
    }
    store = build_store(db=db, default_branch=default_branch)
    assert (await store.read(repository_id=failing.id)).queue.entries == ()
    assert (await store.read(repository_id=healthy.id)).queue.entries == (merges["healthy-repository"].pending_merge,)


async def test_a_stored_value_that_is_not_a_commit_skips_only_its_own_repository(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    broken = await create_repository_node(db=db, branch=default_branch, name="broken-repository")
    healthy = await create_repository_node(db=db, branch=default_branch, name="healthy-repository")
    source_branch = await fork_source_branch(db=db)
    await set_values(db=db, branch=source_branch, repository_id=broken.id, commit="not a commit")
    await set_values(db=db, branch=source_branch, repository_id=healthy.id, commit=SOURCE_COMMIT)
    store = build_store(db=db, default_branch=default_branch)

    workflow = await dispatch_merge(
        db=db, source_branch=source_branch, default_branch=default_branch, sleep=RecordingSleep()
    )

    [merge] = submitted_merges(workflow)
    assert merge.repository_name == "healthy-repository"
    assert merge.pending_merge is not None
    assert merge.pending_merge.source_commit == SOURCE_COMMIT
    assert (await store.read(repository_id=broken.id)).queue == DeliveryQueue()
    assert (await store.read(repository_id=healthy.id)).queue.entries == (merge.pending_merge,)


async def test_a_merge_from_the_remote_branch_that_the_delivery_pushes_to_queues_nothing(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    repository = await create_repository_node(db=db, branch=default_branch, name=REPOSITORY_NAME)
    # The remote branch of the source branch is then the trunk that a delivery pushes to.
    await set_values(db=db, branch=default_branch, repository_id=repository.id, default_branch=SOURCE_BRANCH)
    source_branch = await fork_source_branch(db=db)
    await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)
    sleep = RecordingSleep()

    with capture_logs() as records:
        workflow = await dispatch_merge(db=db, source_branch=source_branch, default_branch=default_branch, sleep=sleep)

    assert submitted_merges(workflow) == []
    assert sleep.delays == []
    assert [record["event"] for record in records if record["log_level"] == "warning"] == [
        f"Skipped the merge of branch {SOURCE_BRANCH} for repository {REPOSITORY_NAME}: the remote branch "
        f"{SOURCE_BRANCH} is the one that a delivery pushes to, so there is nothing to push."
    ]
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue == DeliveryQueue()


async def test_the_retries_of_every_repository_run_at_the_same_time(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    first = await create_repository_node(db=db, branch=default_branch, name="first-repository")
    second = await create_repository_node(db=db, branch=default_branch, name="second-repository")
    source_branch = await fork_source_branch(db=db)
    for repository in (first, second):
        await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)
    sleep = SleepUntilEveryRepositoryWaits(repositories=2)

    workflow = await dispatch_merge(
        db=db,
        source_branch=source_branch,
        default_branch=default_branch,
        sleep=sleep,
        failing_tries={first.id: 1, second.id: 1},
    )

    assert sleep.delays == [2, 2]
    assert {model.repository_name: model.pending_merge_enqueued for model in submitted_merges(workflow)} == {
        "first-repository": True,
        "second-repository": True,
    }


async def test_a_failed_read_of_the_content_still_submits_the_merge_flow_of_every_active_repository(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    changed = await create_repository_node(db=db, branch=default_branch, name="changed-repository")
    unchanged = await create_repository_node(db=db, branch=default_branch, name="unchanged-repository")
    source_branch = await fork_source_branch(db=db)
    await set_values(db=db, branch=source_branch, repository_id=changed.id, commit=SOURCE_COMMIT)
    store = build_store(db=db, default_branch=default_branch)

    with caplog.at_level(logging.ERROR, logger=DISPATCHER_LOGGER):
        workflow = await dispatch_merge(
            db=db,
            # The content read needs the time of the fork, so a branch with no such time makes it raise.
            source_branch=source_branch.model_copy(update={"branched_from": None}),
            default_branch=default_branch,
            sleep=RecordingSleep(),
        )

    submitted = sorted(
        ((call["parameters"]["model"], call["tags"]) for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_MERGE)),
        key=lambda submission: submission[0].repository_name,
    )
    assert submitted == [
        (
            GitRepositoryMerge(
                repository_id=repository.id,
                repository_name=name,
                internal_status=RepositoryInternalStatus.ACTIVE.value,
                source_branch=SOURCE_BRANCH,
                destination_branch=default_branch.name,
                destination_branch_id=str(default_branch.get_uuid()),
                repository_kind=InfrahubKind.REPOSITORY,
                source_commit=commit,
                pending_merge=None,
                pending_merge_enqueued=False,
            ),
            [f"infrahub.app/node/{repository.id}", "infrahub.app/repository-delivery"],
        )
        for name, repository, commit in (
            ("changed-repository", changed, SOURCE_COMMIT),
            ("unchanged-repository", unchanged, TRUNK_COMMIT),
        )
    ]
    assert log_lines(caplog, logger_name=DISPATCHER_LOGGER, level=logging.ERROR) == [
        f"Unable to read which repositories the merge of branch {SOURCE_BRANCH} changes; "
        "the merge flow of each repository reads it again."
    ]
    for repository in (changed, unchanged):
        assert (await store.read(repository_id=repository.id)).queue == DeliveryQueue()


async def test_an_enqueue_that_fails_once_queues_the_merge_after_the_first_delay(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = await create_repository_node(db=db, branch=default_branch, name=REPOSITORY_NAME)
    source_branch = await fork_source_branch(db=db)
    await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)
    sleep = RecordingSleep()

    with caplog.at_level(logging.WARNING, logger=DISPATCHER_LOGGER):
        workflow = await dispatch_merge(
            db=db,
            source_branch=source_branch,
            default_branch=default_branch,
            failing_tries={repository.id: 1},
            sleep=sleep,
        )

    (model,) = submitted_merges(workflow)
    entry = model.pending_merge
    assert entry is not None
    assert model.pending_merge_enqueued is True
    assert sleep.delays == [2]
    assert log_lines(caplog, logger_name=DISPATCHER_LOGGER, level=logging.WARNING) == [
        f"The merge {entry.entry_id} was not queued for the push to repository {REPOSITORY_NAME}; "
        "the next try starts in 2 seconds."
    ]
    assert log_lines(caplog, logger_name=DISPATCHER_LOGGER, level=logging.ERROR) == []
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue.entries == (entry,)
    assert intent.held == HeldRegeneration()


async def test_an_enqueue_that_fails_at_every_try_leaves_the_entry_and_a_full_regeneration_to_the_merge_flow(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = cloned_repository
    source_branch = repository.source_branch
    await set_values(db=db, branch=source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)
    sleep = RecordingSleep()

    with caplog.at_level(logging.WARNING, logger=DISPATCHER_LOGGER):
        workflow = await dispatch_merge(
            db=db,
            source_branch=source_branch,
            default_branch=default_branch,
            failing_tries={repository.id: math.inf},
            sleep=sleep,
        )

    (model,) = submitted_merges(workflow)
    entry = model.pending_merge
    assert entry is not None
    assert (entry.source_branch, entry.source_git_branch, entry.source_commit) == (
        SOURCE_BRANCH,
        SOURCE_BRANCH,
        SOURCE_COMMIT,
    )
    assert model.pending_merge_enqueued is False
    assert sleep.delays == [2, 8, 20]
    assert log_lines(caplog, logger_name=DISPATCHER_LOGGER, level=logging.ERROR) == [
        f"The merge {entry.entry_id} was not queued for the push to repository {REPOSITORY_NAME} after the last try; "
        "the merge flow of the repository queues it, with a full regeneration held."
    ]
    store = build_store(db=db, default_branch=default_branch)
    assert (await store.read(repository_id=repository.id)).queue == DeliveryQueue()

    # A merge can delete its branch before the merge flow runs, so the flow must not need it.
    await BranchDataDeleter(db=db, batch_size=5).delete(branch=source_branch)
    # The attempt then stops at the fetch, so no delivery removes what the flow queued.
    repository.remove_origin()
    await run_merge_flow(dependency_provider=dependency_provider, client=repository.client, model=model)

    intent = await store.read(repository_id=repository.id)
    assert intent.queue.entries == (entry,)
    assert intent.held.widen == HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=1)
    writes = await read_attribute_writes(db=db, branch=default_branch, repository_id=repository.id)
    assert writes[QUEUE].updated_at == writes[HELD_REGENERATION].updated_at


async def test_a_clone_with_no_origin_fails_the_attempt_and_keeps_the_queue(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository
    entry = pending_merge(entry_id=str(uuid4()), source_git_branch=SOURCE_BRANCH)
    store = build_store(db=db, default_branch=default_branch)
    await store.enqueue(repository_id=repository.id, entry=entry, widen=False)
    repository.remove_origin()

    state = await run_merge_flow(
        dependency_provider=dependency_provider,
        client=repository.client,
        model=repository.merge_model(entry=entry, enqueued=True),
    )

    assert state.is_failed()
    assert state.message == f"The delivery to repository {REPOSITORY_NAME} ended with the outcome failed."
    intent = await store.read(repository_id=repository.id)
    assert (intent.status, intent.cause, intent.error) == (
        RepositoryDeliveryStatus.ACTION_REQUIRED,
        RepositoryDeliveryFailureCause.UNCLASSIFIED,
        f"The clone of repository {REPOSITORY_NAME} on this worker has no origin.",
    )
    assert intent.queue.entries == (entry,)
    assert intent.last_delivered_commit is None
    assert repository.clone.get_commit_value(branch_name="main", remote=False) == repository.trunk_commit


async def test_a_merge_flow_that_cannot_queue_its_entry_fails_and_names_the_merge(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
    immediate_delivery_retries: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = cloned_repository
    entry = pending_merge(entry_id=str(uuid4()), source_git_branch=SOURCE_BRANCH)

    # A worker that stopped with the delivery-state lock still holds it.
    async with held_lock(
        lock.registry.get(name=repository.id, namespace=STATE_LOCK_NAMESPACE, ttl=STATE_LOCK_TTL_SECONDS)
    ):
        with caplog.at_level(logging.ERROR, logger=RUN_LOGGER):
            state = await run_merge_flow(
                dependency_provider=dependency_provider,
                client=repository.client,
                model=repository.merge_model(entry=entry, enqueued=False),
            )

    assert state.is_failed()
    assert state.message == f"The delivery to repository {REPOSITORY_NAME} ended with the outcome failed."
    assert log_lines(caplog, logger_name=RUN_LOGGER, level=logging.ERROR) == [
        f"The merge of branch {SOURCE_BRANCH} at commit {SOURCE_COMMIT} was not queued for repository "
        f"{REPOSITORY_NAME} after the last attempt; deliver it by hand."
    ]
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue == DeliveryQueue()
    assert intent.held == HeldRegeneration()


async def test_a_merge_flow_whose_enqueue_fails_once_delivers_the_entry_on_the_retry(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
    immediate_delivery_retries: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = cloned_repository
    source_commit = repository.remote.commit(branch_name=SOURCE_BRANCH, files={"feature.txt": "feature\n"})
    entry = PendingMerge(
        entry_id=str(uuid4()),
        source_branch=SOURCE_BRANCH,
        source_git_branch=SOURCE_BRANCH,
        source_commit=source_commit,
        merged_at=datetime.now(UTC),
    )
    first_failure = (
        f"The merge {entry.entry_id} of branch {SOURCE_BRANCH} was not queued for repository {REPOSITORY_NAME}; "
        "the next attempt queues it."
    )

    # The first attempt waits for the held lock and fails, and its warning frees the lock for the retry.
    async with held_lock(
        lock.registry.get(name=repository.id, namespace=STATE_LOCK_NAMESPACE, ttl=STATE_LOCK_TTL_SECONDS)
    ) as release:
        with (
            caplog.at_level(logging.WARNING, logger=RUN_LOGGER),
            set_on_log(event=release, logger_name=RUN_LOGGER, message=first_failure),
            override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider),
        ):
            state = await run_merge_flow(
                dependency_provider=dependency_provider,
                client=repository.client,
                model=repository.merge_model(entry=entry, enqueued=False),
            )

    assert state.is_completed()
    assert state.message == f"The delivery to repository {REPOSITORY_NAME} ended with the outcome delivered."
    assert log_lines(caplog, logger_name=RUN_LOGGER, level=logging.WARNING) == [first_failure]
    remote = repository.remote.repo
    delivered = remote.commit("main").hexsha
    assert delivered != repository.trunk_commit
    assert remote.is_ancestor(remote.commit(source_commit), remote.commit(delivered))
    assert repository.clone.get_commit_value(branch_name="main", remote=False) == delivered
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue.entries == ()
    assert intent.queue.removed_entry_ids == (entry.entry_id,)
    assert intent.status == RepositoryDeliveryStatus.NONE
    assert intent.last_delivered_commit == delivered


async def test_a_merge_flow_whose_entry_is_refused_holds_no_full_regeneration(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository
    entry = pending_merge(entry_id=str(uuid4()), source_git_branch=SOURCE_BRANCH)
    store = build_store(db=db, default_branch=default_branch)
    # A try of the branch merge queued the entry and then raised, so the flag says that it is not queued.
    await store.enqueue(repository_id=repository.id, entry=entry, widen=False)
    # The attempt then stops at the fetch, so no delivery removes a marker that the flow held.
    repository.remove_origin()

    await run_merge_flow(
        dependency_provider=dependency_provider,
        client=repository.client,
        model=repository.merge_model(entry=entry, enqueued=False),
    )

    intent = await store.read(repository_id=repository.id)
    assert intent.queue.entries == (entry,)
    assert intent.held == HeldRegeneration()


async def test_a_merge_flow_with_no_entry_queues_the_entry_it_builds_with_a_full_regeneration(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository
    await set_values(db=db, branch=repository.source_branch, repository_id=repository.id, commit=SOURCE_COMMIT)
    # The attempt then stops at the fetch, so no delivery removes what the flow queued.
    repository.remove_origin()

    await run_merge_flow(
        dependency_provider=dependency_provider,
        client=repository.client,
        model=repository.merge_model(entry=None, enqueued=False),
    )

    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert [
        (entry.source_branch, entry.source_git_branch, entry.source_commit, entry.delete_source_git_branch)
        for entry in intent.queue.entries
    ] == [(SOURCE_BRANCH, SOURCE_BRANCH, SOURCE_COMMIT, False)]
    assert intent.held.widen == HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=1)
    writes = await read_attribute_writes(db=db, branch=default_branch, repository_id=repository.id)
    assert writes[QUEUE].updated_at == writes[HELD_REGENERATION].updated_at


async def test_a_merge_flow_whose_source_branch_is_gone_queues_the_commit_of_its_submission(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository
    repository.remove_origin()
    model = repository.merge_model(entry=None, enqueued=False).model_copy(
        update={"source_branch": "deleted-branch", "source_commit": SOURCE_COMMIT}
    )

    await run_merge_flow(dependency_provider=dependency_provider, client=repository.client, model=model)

    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert [(entry.source_branch, entry.source_git_branch, entry.source_commit) for entry in intent.queue.entries] == [
        ("deleted-branch", "deleted-branch", SOURCE_COMMIT)
    ]
    assert intent.held.widen == HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=1)


async def test_a_merge_flow_whose_source_branch_is_gone_queues_nothing_for_the_recorded_commit(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository
    model = repository.merge_model(entry=None, enqueued=False).model_copy(
        update={"source_branch": "deleted-branch", "source_commit": repository.trunk_commit}
    )

    state = await run_merge_flow(dependency_provider=dependency_provider, client=repository.client, model=model)

    assert state.is_completed()
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue == DeliveryQueue()
    assert intent.held == HeldRegeneration()


async def test_a_merge_flow_whose_entry_the_branch_merge_queued_never_queues_it_again(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    """A user can abandon the queue while the run waits, so the run must not put the entry back."""
    repository = cloned_repository
    entry = pending_merge(entry_id=str(uuid4()), source_git_branch=SOURCE_BRANCH)

    state = await run_merge_flow(
        dependency_provider=dependency_provider,
        client=repository.client,
        model=repository.merge_model(entry=entry, enqueued=True),
    )

    assert state.is_completed()
    assert state.message == f"The delivery to repository {REPOSITORY_NAME} ended with the outcome nothing-pending."
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue == DeliveryQueue()
    assert intent.held == HeldRegeneration()


async def test_a_merge_flow_with_no_entry_and_no_content_queues_nothing(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository

    state = await run_merge_flow(
        dependency_provider=dependency_provider,
        client=repository.client,
        model=repository.merge_model(entry=None, enqueued=False),
    )

    assert state.is_completed()
    assert state.message == f"The delivery to repository {REPOSITORY_NAME} ended with the outcome nothing-pending."
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue == DeliveryQueue()
    assert intent.held == HeldRegeneration()


async def test_a_merge_flow_whose_source_branch_is_gone_fails_and_says_how_to_push_the_merge_by_hand(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = cloned_repository
    model = repository.merge_model(entry=None, enqueued=False).model_copy(update={"source_branch": "deleted-branch"})
    expected = (
        f"The branch deleted-branch was deleted before its merge was queued, so repository {REPOSITORY_NAME} does "
        "not push that merge to its remote. The last commit of the branch on this worker is unknown. Merge the "
        "branch deleted-branch into the branch main on the remote by hand."
    )

    with caplog.at_level(logging.ERROR, logger=FLOW_LOGGER):
        state = await run_merge_flow(dependency_provider=dependency_provider, client=repository.client, model=model)

    assert state.is_failed()
    assert state.message == expected
    assert log_lines(caplog, logger_name=FLOW_LOGGER, level=logging.ERROR) == [
        expected,
        f"Finished in state Failed({expected!r})",
    ]
    intent = await build_store(db=db, default_branch=default_branch).read(repository_id=repository.id)
    assert intent.queue == DeliveryQueue()


async def test_a_retry_that_waits_for_a_running_attempt_finds_nothing_to_push(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    recording_lock_timeline: LockTimeline,
    cloned_repository: ClonedRepository,
) -> None:
    repository = cloned_repository
    store = build_store(db=db, default_branch=default_branch)
    await store.enqueue(repository_id=repository.id, entry=pending_merge(entry_id=str(uuid4())), widen=False)
    repository_lock = lock.registry.get(name=REPOSITORY_NAME, namespace=REPOSITORY_LOCK_NAMESPACE)

    async with held_lock(repository_lock):
        retry = asyncio.create_task(
            run_retry_flow(
                dependency_provider=dependency_provider, client=repository.client, repository_id=repository.id
            )
        )
        async with asyncio.timeout(30):
            while recording_lock_timeline.waiting(repository_lock.name) != 1:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
        # The running attempt settles the queue before it lets the waiting retry in.
        snapshot = await store.start_attempt(repository_id=repository.id)
        await store.settle_delivery(repository_id=repository.id, snapshot=snapshot, delivered_commit=None)

    state = await retry
    assert (state.is_completed(), state.message) == (
        True,
        f"The delivery to repository {REPOSITORY_NAME} ended with the outcome nothing-pending.",
    )
    intent = await store.read(repository_id=repository.id)
    assert (intent.status, intent.queue.entries) == (RepositoryDeliveryStatus.NONE, ())
    assert repository.clone.get_commit_value(branch_name="main", remote=False) == repository.trunk_commit


@dataclass
class BranchDeletionCase:
    name: str
    queued_git_branch: str
    """The remote branch that the queued merge comes from."""
    state_lock_held: bool
    flagged: bool
    remote_branches: list[str]
    notified: list[str]
    logged: list[tuple[int, str, type[BaseException] | None]]
    """The level, the message and the type of the logged error of each warning or error."""


BRANCH_DELETION_CASES: list[BranchDeletionCase] = [
    BranchDeletionCase(
        name="a_queued_merge_comes_from_the_branch",
        queued_git_branch=SOURCE_BRANCH,
        state_lock_held=False,
        flagged=True,
        remote_branches=[SOURCE_BRANCH, "main"],
        notified=[],
        logged=[
            (
                logging.WARNING,
                f"Did not delete the Git branch '{SOURCE_BRANCH}' from repository '{REPOSITORY_NAME}', because a "
                "pending delivery of the repository needs it. The delivery deletes the branch after it pushes the "
                "merge, unless another queued merge comes from it. If the delivery is abandoned, the branch stays.",
                None,
            )
        ],
    ),
    BranchDeletionCase(
        name="no_queued_merge_comes_from_the_branch",
        queued_git_branch="other-feature",
        state_lock_held=False,
        flagged=False,
        remote_branches=["main"],
        notified=[SOURCE_BRANCH],
        logged=[],
    ),
    BranchDeletionCase(
        name="the_check_for_a_queued_merge_fails",
        queued_git_branch=SOURCE_BRANCH,
        state_lock_held=True,
        flagged=False,
        remote_branches=[SOURCE_BRANCH, "main"],
        notified=[],
        logged=[
            (
                logging.ERROR,
                f"Did not delete the Git branch '{SOURCE_BRANCH}' from repository '{REPOSITORY_NAME}', because the "
                "check for a pending delivery that needs the branch failed. Delete the branch from the remote by hand "
                "when the repository has no pending delivery.",
                DeliveryStateUnavailableError,
            )
        ],
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in BRANCH_DELETION_CASES])
async def test_a_branch_deletion_keeps_the_remote_branch_while_a_queued_merge_comes_from_it(
    case: BranchDeletionCase,
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture: None,
    dependency_provider: Provider,
    cloned_repository: ClonedRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = cloned_repository
    repository.remote.create_branch(SOURCE_BRANCH)
    await repository.clone.fetch()
    store = build_store(db=db, default_branch=default_branch)
    entry = pending_merge(entry_id=str(uuid4()), source_git_branch=case.queued_git_branch)
    queued = await store.enqueue(repository_id=repository.id, entry=entry, widen=False)
    bus = BusRecorder()

    @flow(name="test-delete-a-git-branch-of-one-repository")
    async def delete_the_git_branch() -> None:
        await git_branch_delete(
            client=repository.client,
            branch=SOURCE_BRANCH,
            repository_id=repository.id,
            repository_name=REPOSITORY_NAME,
            repository_location=str(repository.remote.directory),
        )

    state_lock = (
        held_lock(lock.registry.get(name=repository.id, namespace=STATE_LOCK_NAMESPACE, ttl=STATE_LOCK_TTL_SECONDS))
        if case.state_lock_held
        else nullcontext()
    )
    with (
        override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider),
        caplog.at_level(logging.WARNING, logger=TASK_LOGGER),
    ):
        async with state_lock:
            await delete_the_git_branch()

    assert sorted(head.name for head in repository.remote.repo.heads) == case.remote_branches
    assert [(type(message), message.model_dump(exclude={"meta"})) for message in bus.messages] == [
        (
            RefreshGitRepositoryBranchDeleted,
            {
                "repository_id": repository.id,
                "repository_name": REPOSITORY_NAME,
                "repository_kind": InfrahubKind.REPOSITORY,
                "branch_name": branch_name,
            },
        )
        for branch_name in case.notified
    ]
    assert [
        (record.levelno, record.getMessage(), record.exc_info[0] if record.exc_info else None)
        for record in caplog.records
        if record.name == TASK_LOGGER and record.levelno >= logging.WARNING
    ] == case.logged
    assert await store.read(repository_id=repository.id) == replace(
        queued,
        queue=queued.queue.model_copy(
            update={"entries": (entry.model_copy(update={"delete_source_git_branch": case.flagged}),)}
        ),
    )
