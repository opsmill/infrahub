from __future__ import annotations

import logging
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from prefect.client.schemas.filters import (
    FlowFilter,
    FlowRunFilter,
    FlowRunFilterState,
    FlowRunFilterStateType,
    FlowRunFilterTags,
)
from prefect.client.schemas.objects import FlowRun, StateType, TaskRun
from prefect.states import Failed

from infrahub.auth.session import AnonymousSession
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import RepositoryDeliveryFailureCause, RepositoryDeliveryStatus
from infrahub.exceptions import (
    DatabaseError,
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryNotFoundError,
    RepositoryPermissionError,
    RepositoryPushRejectedError,
    RepositoryTLSError,
    ValidationError,
)
from infrahub.git.models import GitRepositoryDeliveryRetry, PushRejectionReason
from infrahub.git.tasks import deliver_pending_merges
from infrahub.git.writeback.constants import STALE_AFTER_SECONDS
from infrahub.git.writeback.models import (
    DeliveryAttemptResult,
    DeliveryFailure,
    DeliveryOutcome,
    DeliveryProgress,
    DeliveryQueue,
    HeldItem,
    HeldRegeneration,
    PendingMerge,
    ReleaseLease,
    WritebackIntent,
)
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.recovery import DeliveryRecoveryCheck
from infrahub.git.writeback.runs import PrefectDeliveryRunQuery, is_retryable_delivery_failure, next_retry_delay
from infrahub.git.writeback.service import REPOSITORY_LOCK_NAMESPACE, RepositoryWritebackService, RetryableDeliveryError
from infrahub.lock import InfrahubLockRegistry
from infrahub.workflows.catalogue import GIT_REPOSITORY_DELIVERY_RETRY
from tests.adapters.workflow import ContextRecordingWorkflow
from tests.unit.git.writeback.fakes import (
    FailingDeliveryRunQuery,
    FixedClock,
    InMemoryDeliveryGit,
    InMemoryDeliveryRunQuery,
    InMemoryDeliveryState,
    RecordingRegenerationReleaser,
)

if TYPE_CHECKING:
    from prefect.client.schemas.sorting import FlowRunSort

REPOSITORY = RepositoryRef(id="repository-1", name="net-repo", destination_git_branch="main")
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
TASK_RUN = TaskRun(task_key="git-repository-deliver", dynamic_key="0")

TRUNK = "a" * 40
FEATURE = "b" * 40
UPSTREAM = "d" * 40
"""A commit that another client pushed onto the trunk, so the delivery owes an import."""

ENTRY = PendingMerge(
    entry_id="merge-1", source_branch="add-vlan", source_git_branch="feature", source_commit=FEATURE, merged_at=NOW
)
DATABASE_DOWN = "Unable to connect to the database"


@dataclass
class Rig:
    state: InMemoryDeliveryState
    git: InMemoryDeliveryGit
    releaser: RecordingRegenerationReleaser
    service: RepositoryWritebackService

    def fail(self, *, step: str, error: Exception) -> None:
        if step == "enqueue":
            self.state.failures[step] = [error]
        elif step == "release":
            self.releaser.failures.append(error)
        else:
            self.git.failures[step] = [error]


@pytest.fixture
def rig() -> Rig:
    clock = FixedClock(now=NOW)
    state = InMemoryDeliveryState(clock=clock, repository_names={REPOSITORY.id: REPOSITORY.name})
    git = InMemoryDeliveryGit(destination_git_branch=REPOSITORY.destination_git_branch, head=TRUNK)
    for commit in (FEATURE, UPSTREAM):
        git.add_commit(commit=commit, parents=(TRUNK,))
    git.remote_heads.update({"main": UPSTREAM, "feature": FEATURE})
    releaser = RecordingRegenerationReleaser()
    service = RepositoryWritebackService(
        repository=REPOSITORY,
        state=state,
        git=git,
        releaser=releaser,
        lock_registry=InfrahubLockRegistry(local_only=True),
        clock=clock,
    )
    return Rig(state=state, git=git, releaser=releaser, service=service)


async def deliver_first_attempt(service: RepositoryWritebackService) -> DeliveryAttemptResult:
    """Run the attempt that the first run of the delivery task runs, with the retries of the task."""
    retry_delay = next_retry_delay(
        run_count=1,
        retries=deliver_pending_merges.retries,
        retry_delay_seconds=deliver_pending_merges.retry_delay_seconds,
    )
    return await service.deliver(final_attempt=retry_delay is None, manual=False, entry=ENTRY, retry_delay=retry_delay)


@dataclass
class CauseCase:
    name: str
    step: str
    """The call that raises: `enqueue` of the state, `release` of the releaser, or a method of the Git port."""
    error: Exception
    failure: DeliveryFailure
    status: RepositoryDeliveryStatus
    retry_due_at: datetime | None


FIRST_RETRY_DUE_AT = datetime(2026, 10, 8, 12, 0, 30, tzinfo=UTC)

CAUSE_CASES: list[CauseCase] = [
    CauseCase(
        name="remote_unreachable_is_retried",
        step="push",
        error=RepositoryConnectionError(identifier="net-repo", message="The remote net-repo does not answer."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE,
            retryable=True,
            message="The remote net-repo does not answer.",
        ),
        status=RepositoryDeliveryStatus.PENDING,
        retry_due_at=FIRST_RETRY_DUE_AT,
    ),
    CauseCase(
        name="remote_advanced_is_retried",
        step="push",
        error=RepositoryPushRejectedError(
            identifier="net-repo",
            reason=PushRejectionReason.NON_FAST_FORWARD,
            remote_message="",
            message="The remote refused the push to main, because main moved.",
        ),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_ADVANCED,
            retryable=True,
            message="The remote refused the push to main, because main moved.",
        ),
        status=RepositoryDeliveryStatus.PENDING,
        retry_due_at=FIRST_RETRY_DUE_AT,
    ),
    CauseCase(
        name="failed_record_is_retried",
        step="record",
        error=DatabaseError(message=DATABASE_DOWN),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.RECORD_FAILED, retryable=True, message=DATABASE_DOWN
        ),
        status=RepositoryDeliveryStatus.PENDING,
        retry_due_at=FIRST_RETRY_DUE_AT,
    ),
    CauseCase(
        name="interrupted_import_is_retried",
        step="import_at",
        error=DatabaseError(message=DATABASE_DOWN),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED, retryable=True, message=DATABASE_DOWN
        ),
        status=RepositoryDeliveryStatus.PENDING,
        retry_due_at=FIRST_RETRY_DUE_AT,
    ),
    CauseCase(
        name="failed_release_is_retried_with_no_cause",
        step="release",
        error=RuntimeError("The generator run did not start."),
        failure=DeliveryFailure(
            cause=None, retryable=True, message="The release step of the delivery failed with RuntimeError."
        ),
        status=RepositoryDeliveryStatus.NONE,
        retry_due_at=FIRST_RETRY_DUE_AT,
    ),
    CauseCase(
        name="failed_enqueue_is_retried_and_records_nothing",
        step="enqueue",
        error=DatabaseError(message=DATABASE_DOWN),
        failure=DeliveryFailure(cause=None, retryable=True, message=DATABASE_DOWN),
        status=RepositoryDeliveryStatus.NONE,
        retry_due_at=None,
    ),
    CauseCase(
        name="missing_repository_fails_at_once",
        step="fetch",
        error=RepositoryNotFoundError(identifier="net-repo", message="The remote has no repository net-repo."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.NOT_FOUND,
            retryable=False,
            message="The remote has no repository net-repo.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        retry_due_at=None,
    ),
    CauseCase(
        name="refused_certificate_fails_at_once",
        step="fetch",
        error=RepositoryTLSError(identifier="net-repo", message="The certificate of net-repo is not trusted."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CERTIFICATE,
            retryable=False,
            message="The certificate of net-repo is not trusted.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        retry_due_at=None,
    ),
    CauseCase(
        name="refused_credentials_fail_at_once",
        step="push",
        error=RepositoryCredentialsError(identifier="net-repo", message="The token of net-repo is not valid."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CREDENTIALS,
            retryable=False,
            message="The token of net-repo is not valid.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        retry_due_at=None,
    ),
    CauseCase(
        name="refused_write_access_fails_at_once",
        step="push",
        error=RepositoryPermissionError(identifier="net-repo", message="The token of net-repo can only read."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.PERMISSION,
            retryable=False,
            message="The token of net-repo can only read.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        retry_due_at=None,
    ),
    CauseCase(
        name="invalid_content_fails_the_import_at_once",
        step="import_at",
        error=ValidationError(input_value="The artifact definition net-config has no target group."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_FAILED,
            retryable=False,
            message="The artifact definition net-config has no target group.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        retry_due_at=None,
    ),
    CauseCase(
        name="unclassified_error_fails_at_once",
        step="replay",
        error=RuntimeError("The worktree is locked."),
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
            retryable=False,
            message="The replay step of the delivery failed with RuntimeError.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        retry_due_at=None,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CAUSE_CASES])
async def test_a_first_attempt_retries_only_a_failure_that_a_later_attempt_can_fix(rig: Rig, case: CauseCase) -> None:
    rig.fail(step=case.step, error=case.error)

    if case.failure.retryable:
        with pytest.raises(RetryableDeliveryError, match=rf"^{re.escape(case.failure.message)}$") as raised:
            await deliver_first_attempt(service=rig.service)
        assert raised.value.failure == case.failure
        error: Exception = raised.value
    else:
        result = await deliver_first_attempt(service=rig.service)
        assert (result.outcome, result.failure) == (DeliveryOutcome.FAILED, case.failure)
        error = case.error

    assert deliver_pending_merges.retry_condition_fn is is_retryable_delivery_failure
    assert (
        is_retryable_delivery_failure(task=deliver_pending_merges, task_run=TASK_RUN, state=Failed(data=error))
        is case.failure.retryable
    )
    intent = rig.state.intents[REPOSITORY.id]
    assert (intent.status, intent.cause, intent.progress.retry_due_at) == (
        case.status,
        case.failure.cause,
        case.retry_due_at,
    )


@dataclass
class RetryDelayCase:
    name: str
    run_count: int
    retries: int
    retry_delay_seconds: float | list[float] | None
    expected: timedelta | None
    """None when the attempt is the final one."""


RETRY_DELAY_CASES: list[RetryDelayCase] = [
    RetryDelayCase(
        name="first_attempt_waits_the_first_delay",
        run_count=1,
        retries=3,
        retry_delay_seconds=[30, 120, 300],
        expected=timedelta(seconds=30),
    ),
    RetryDelayCase(
        name="middle_attempt_waits_its_own_delay",
        run_count=2,
        retries=3,
        retry_delay_seconds=[30, 120, 300],
        expected=timedelta(seconds=120),
    ),
    RetryDelayCase(
        name="last_attempt_with_a_retry_waits_the_last_delay",
        run_count=3,
        retries=3,
        retry_delay_seconds=[30, 120, 300],
        expected=timedelta(seconds=300),
    ),
    RetryDelayCase(
        name="final_attempt_has_no_retry",
        run_count=4,
        retries=3,
        retry_delay_seconds=[30, 120, 300],
        expected=None,
    ),
    RetryDelayCase(
        name="single_delay_is_the_wait_of_every_retry",
        run_count=2,
        retries=3,
        retry_delay_seconds=5,
        expected=timedelta(seconds=5),
    ),
    RetryDelayCase(
        name="list_shorter_than_the_retries_repeats_its_last_delay",
        run_count=3,
        retries=3,
        retry_delay_seconds=[10, 20],
        expected=timedelta(seconds=20),
    ),
    RetryDelayCase(
        name="no_delay_retries_at_once",
        run_count=1,
        retries=3,
        retry_delay_seconds=None,
        expected=timedelta(0),
    ),
    RetryDelayCase(
        name="zero_delay_retries_at_once",
        run_count=2,
        retries=3,
        retry_delay_seconds=0,
        expected=timedelta(0),
    ),
    RetryDelayCase(
        name="no_retries_make_the_first_attempt_final",
        run_count=1,
        retries=0,
        retry_delay_seconds=[30],
        expected=None,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RETRY_DELAY_CASES])
def test_the_wait_before_the_next_attempt_follows_the_retries_of_the_task(case: RetryDelayCase) -> None:
    delay = next_retry_delay(
        run_count=case.run_count, retries=case.retries, retry_delay_seconds=case.retry_delay_seconds
    )

    assert delay == case.expected


@dataclass
class WaitingRetryCase:
    name: str
    manual: bool
    retry_due_at: datetime
    """When the retry of another attempt chain is due."""
    deferred: bool


WAITING_RETRY_CASES: list[WaitingRetryCase] = [
    WaitingRetryCase(
        name="automatic_attempt_leaves_the_queue_to_a_retry_due_later",
        manual=False,
        retry_due_at=NOW + timedelta(seconds=30),
        deferred=True,
    ),
    WaitingRetryCase(
        name="manual_attempt_runs_while_a_retry_is_due_later",
        manual=True,
        retry_due_at=NOW + timedelta(seconds=30),
        deferred=False,
    ),
    WaitingRetryCase(
        name="automatic_attempt_runs_when_the_retry_is_due_now",
        manual=False,
        retry_due_at=NOW,
        deferred=False,
    ),
    WaitingRetryCase(
        name="automatic_attempt_runs_when_the_retry_was_due_earlier",
        manual=False,
        retry_due_at=NOW - timedelta(seconds=1),
        deferred=False,
    ),
]
DELIVERED_COMMIT = f"{UPSTREAM}+{FEATURE}"


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in WAITING_RETRY_CASES])
async def test_an_automatic_attempt_leaves_the_queue_to_the_retry_that_another_chain_waits_for(
    rig: Rig, case: WaitingRetryCase, caplog: pytest.LogCaptureFixture
) -> None:
    initial = rig.state.intents[REPOSITORY.id]
    rig.state.intents[REPOSITORY.id] = replace(initial, progress=DeliveryProgress(retry_due_at=case.retry_due_at))

    with caplog.at_level(logging.INFO, logger=RUN_LOGGER):
        result = await rig.service.deliver(
            final_attempt=False, manual=case.manual, entry=ENTRY, retry_delay=timedelta(seconds=30)
        )

    intent = rig.state.intents[REPOSITORY.id]
    if case.deferred:
        assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DEFERRED)
        assert intent.queue.entries == (ENTRY,)
        assert intent.progress.retry_due_at == case.retry_due_at
        assert rig.state.calls == ["enqueue", "read"]
        assert rig.git.calls == []
        assert rig.service.lock_registry.locks == {}
        assert [record.getMessage() for record in caplog.records if record.name == RUN_LOGGER] == [
            "Delivery attempt of repository net-repo starts (final attempt: False, manual: False).",
            "The queue of repository net-repo holds the merge merge-1 of branch add-vlan.",
            "Left the queue of repository net-repo to the retry that is due at 2026-10-08 12:00:30+00:00.",
        ]
    else:
        assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=DELIVERED_COMMIT)
        assert intent.queue.entries == ()
        assert intent.progress.retry_due_at is None
        assert rig.git.pushed == [DELIVERED_COMMIT]


@dataclass(frozen=True)
class FlowRunsRead:
    flow_filter: FlowFilter | None
    flow_run_filter: FlowRunFilter | None
    limit: int | None
    offset: int
    sort: FlowRunSort | None


class RecordingFlowRunClient:
    """Records every argument of each read of flow runs, in order, and returns the runs that the test gives."""

    def __init__(self, *, runs: list[FlowRun]) -> None:
        self.runs = runs
        self.reads: list[FlowRunsRead] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        self.reads.append(
            FlowRunsRead(
                flow_filter=flow_filter, flow_run_filter=flow_run_filter, limit=limit, offset=offset, sort=sort
            )
        )
        return self.runs


@dataclass
class QueuedRunCase:
    name: str
    runs: list[FlowRun]
    expected: bool


QUEUED_RUN_CASES: list[QueuedRunCase] = [
    QueuedRunCase(name="returned_run_waits", runs=[FlowRun(flow_id=uuid4(), name="deliver")], expected=True),
    QueuedRunCase(name="no_returned_run_means_none_waits", runs=[], expected=False),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in QUEUED_RUN_CASES])
async def test_the_queued_run_query_asks_once_for_a_run_with_both_delivery_tags_that_waits_to_start(
    case: QueuedRunCase,
) -> None:
    client = RecordingFlowRunClient(runs=case.runs)

    queued = await PrefectDeliveryRunQuery(client=client).has_queued_run(repository_id=REPOSITORY.id)

    assert queued is case.expected
    assert client.reads == [
        FlowRunsRead(
            flow_filter=None,
            flow_run_filter=FlowRunFilter(
                tags=FlowRunFilterTags(all_=["infrahub.app/node/repository-1", "infrahub.app/repository-delivery"]),
                state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.SCHEDULED, StateType.PENDING])),
            ),
            limit=1,
            offset=0,
            sort=None,
        )
    ]


CHECK_NOW = datetime(2026, 10, 8, 13, 0, tzinfo=UTC)
STALE_AFTER = timedelta(seconds=STALE_AFTER_SECONDS)
LONG_AGO = CHECK_NOW - STALE_AFTER - timedelta(seconds=1)
"""Just older than the stale bound."""
AT_THE_STALE_BOUND = CHECK_NOW - STALE_AFTER
RECOVERY_CONTEXT = InfrahubContext(
    branch=BranchContext(name="main", id="default-branch-id"), account=AnonymousSession()
)
DELIVERY_TAGS = ["infrahub.app/node/repository-1", "infrahub.app/repository-delivery"]
HELD_DEFINITION = HeldItem(id="artifact-definition-1", hold_seq=1)
RUN_LOGGER = "infrahub.tasks"


def delivery_state(
    *,
    status: RepositoryDeliveryStatus,
    entries: tuple[PendingMerge, ...],
    last_progress_at: datetime | None,
    retry_due_at: datetime | None = None,
    held: HeldRegeneration | None = None,
) -> WritebackIntent:
    return WritebackIntent(
        repository_id=REPOSITORY.id,
        status=status,
        cause=None,
        error=None,
        queue=DeliveryQueue(version=len(entries), entries=entries),
        held=held or HeldRegeneration(),
        progress=DeliveryProgress(last_progress_at=last_progress_at, retry_due_at=retry_due_at),
        last_delivered_commit=None,
    )


def held_definition(*, lease_expires_at: datetime | None = None) -> HeldRegeneration:
    """One held artifact definition, named by a release lease that expires at the time given, if one is given."""
    leases = (
        ()
        if lease_expires_at is None
        else (ReleaseLease(lease_id="lease-1", expires_at=lease_expires_at, artifact_definitions=(HELD_DEFINITION,)),)
    )
    return HeldRegeneration(next_hold_seq=2, artifact_definitions=(HELD_DEFINITION,), release_leases=leases)


@dataclass
class CheckRig:
    state: InMemoryDeliveryState
    workflow: ContextRecordingWorkflow
    runs: InMemoryDeliveryRunQuery
    lock_registry: InfrahubLockRegistry
    check: DeliveryRecoveryCheck


@pytest.fixture
def check_rig() -> CheckRig:
    clock = FixedClock(now=CHECK_NOW)
    state = InMemoryDeliveryState(clock=clock, repository_names={REPOSITORY.id: REPOSITORY.name})
    workflow = ContextRecordingWorkflow()
    runs = InMemoryDeliveryRunQuery()
    lock_registry = InfrahubLockRegistry(local_only=True)
    check = DeliveryRecoveryCheck(
        state=state, workflow=workflow, runs=runs, lock_registry=lock_registry, clock=clock, context=RECOVERY_CONTEXT
    )
    return CheckRig(state=state, workflow=workflow, runs=runs, lock_registry=lock_registry, check=check)


async def run_check(rig: CheckRig, *, lock_held: bool = False) -> bool:
    async with AsyncExitStack() as stack:
        if lock_held:
            await stack.enter_async_context(
                rig.lock_registry.get(name=REPOSITORY.name, namespace=REPOSITORY_LOCK_NAMESPACE)
            )
        return await rig.check.run(repository=REPOSITORY)


STALE_SUBMISSION_LOG = "Submitted a delivery run of repository net-repo, whose delivery lost its attempt."
HELD_SUBMISSION_LOG = (
    "Submitted a delivery run of repository net-repo, whose held regeneration waits behind an empty queue."
)
EXPECTED_SUBMISSION = {
    "kind": "submit",
    "workflow": GIT_REPOSITORY_DELIVERY_RETRY,
    "parameters": {
        "model": GitRepositoryDeliveryRetry(repository_id=REPOSITORY.id, repository_name=REPOSITORY.name, manual=False)
    },
    "tags": DELIVERY_TAGS,
}


@dataclass
class RecoveryCase:
    name: str
    intent: WritebackIntent
    submits: bool
    asks: bool
    """Whether the check asks the orchestrator for a delivery run that waits to start."""
    lock_held: bool = False
    run_queued: bool = False
    submission_log: str | None = None
    """The info line that names why the check submitted."""


RECOVERY_CASES: list[RecoveryCase] = [
    RecoveryCase(
        name="stale_delivery_is_recovered",
        intent=delivery_state(status=RepositoryDeliveryStatus.PENDING, entries=(ENTRY,), last_progress_at=LONG_AGO),
        submits=True,
        asks=True,
        submission_log=STALE_SUBMISSION_LOG,
    ),
    RecoveryCase(
        name="repository_with_nothing_pending_makes_no_query",
        intent=delivery_state(status=RepositoryDeliveryStatus.NONE, entries=(), last_progress_at=None),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="delivery_that_waits_for_a_user_action_is_not_stale",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.ACTION_REQUIRED, entries=(ENTRY,), last_progress_at=LONG_AGO
        ),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="retry_due_in_the_future_owns_the_delivery",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.PENDING,
            entries=(ENTRY,),
            last_progress_at=LONG_AGO,
            retry_due_at=CHECK_NOW + timedelta(seconds=60),
        ),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="progress_at_the_stale_bound_is_recent",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.PENDING, entries=(ENTRY,), last_progress_at=AT_THE_STALE_BOUND
        ),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="held_repository_lock_means_an_attempt_still_works",
        intent=delivery_state(status=RepositoryDeliveryStatus.PENDING, entries=(ENTRY,), last_progress_at=LONG_AGO),
        lock_held=True,
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="run_that_waits_in_the_queue_gets_no_second_submission",
        intent=delivery_state(status=RepositoryDeliveryStatus.PENDING, entries=(ENTRY,), last_progress_at=LONG_AGO),
        run_queued=True,
        submits=False,
        asks=True,
    ),
    RecoveryCase(
        # The orchestrator still shows the run as running, which the query does not count as waiting.
        name="running_run_with_no_progress_and_a_free_lock_is_stale",
        intent=delivery_state(status=RepositoryDeliveryStatus.PENDING, entries=(ENTRY,), last_progress_at=LONG_AGO),
        submits=True,
        asks=True,
        submission_log=STALE_SUBMISSION_LOG,
    ),
    RecoveryCase(
        name="crashed_run_whose_retry_was_due_is_stale",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.PENDING,
            entries=(ENTRY,),
            last_progress_at=LONG_AGO,
            retry_due_at=LONG_AGO + timedelta(seconds=30),
        ),
        submits=True,
        asks=True,
        submission_log=STALE_SUBMISSION_LOG,
    ),
    RecoveryCase(
        name="uncovered_held_work_behind_an_empty_queue_is_released",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.NONE,
            entries=(),
            last_progress_at=LONG_AGO,
            held=held_definition(lease_expires_at=CHECK_NOW - timedelta(seconds=1)),
        ),
        submits=True,
        asks=True,
        submission_log=HELD_SUBMISSION_LOG,
    ),
    RecoveryCase(
        # A merge flow that crashed before its first attempt never moved the progress time.
        name="held_work_behind_an_empty_queue_that_never_progressed_is_released",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.NONE, entries=(), last_progress_at=None, held=held_definition()
        ),
        submits=True,
        asks=True,
        submission_log=HELD_SUBMISSION_LOG,
    ),
    RecoveryCase(
        name="held_work_that_a_live_lease_covers_gets_no_submission",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.NONE,
            entries=(),
            last_progress_at=LONG_AGO,
            held=held_definition(lease_expires_at=CHECK_NOW + timedelta(seconds=60)),
        ),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="held_work_with_recent_progress_waits",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.NONE,
            entries=(),
            last_progress_at=AT_THE_STALE_BOUND,
            held=held_definition(),
        ),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="held_work_behind_a_queue_that_waits_for_a_user_action_gets_no_submission",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.ACTION_REQUIRED,
            entries=(ENTRY,),
            last_progress_at=LONG_AGO,
            held=held_definition(),
        ),
        submits=False,
        asks=False,
    ),
    RecoveryCase(
        name="held_work_with_a_run_that_waits_in_the_queue_gets_no_submission",
        intent=delivery_state(
            status=RepositoryDeliveryStatus.NONE, entries=(), last_progress_at=LONG_AGO, held=held_definition()
        ),
        run_queued=True,
        submits=False,
        asks=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RECOVERY_CASES])
async def test_the_recovery_check_submits_one_delivery_run_only_when_nothing_else_will_deliver(
    check_rig: CheckRig, case: RecoveryCase, caplog: pytest.LogCaptureFixture
) -> None:
    check_rig.state.intents[REPOSITORY.id] = case.intent
    if case.run_queued:
        check_rig.runs.queued.add(REPOSITORY.id)

    with caplog.at_level(logging.INFO, logger=RUN_LOGGER):
        submitted = await run_check(check_rig, lock_held=case.lock_held)

    assert submitted is case.submits
    assert [record.getMessage() for record in caplog.records if record.name == RUN_LOGGER] == (
        [case.submission_log] if case.submits else []
    )
    assert check_rig.runs.asked == ([REPOSITORY.id] if case.asks else [])
    intent = check_rig.state.intents[REPOSITORY.id]
    if case.submits:
        assert check_rig.workflow.submit_calls == [EXPECTED_SUBMISSION]
        assert check_rig.workflow.contexts == [RECOVERY_CONTEXT]
        assert check_rig.state.calls == ["read", "touch"]
        assert intent == replace(
            case.intent, progress=case.intent.progress.model_copy(update={"last_progress_at": CHECK_NOW})
        )
    else:
        assert check_rig.workflow.submit_calls == []
        assert check_rig.state.calls == ["read"]
        assert intent == case.intent


STALE_INTENT = delivery_state(status=RepositoryDeliveryStatus.PENDING, entries=(ENTRY,), last_progress_at=LONG_AGO)


@dataclass
class QueryFailureCase:
    name: str
    error: Exception
    log_level: int
    log_message: str
    traceback: type[Exception] | None
    """The type of the error whose traceback the log line carries, None when it carries none."""


ORCHESTRATOR_WARNING = (
    "Could not ask the orchestrator whether a delivery run of repository net-repo waits, so none is submitted: "
    "The orchestrator does not answer"
)
QUERY_FAILURE_CASES: list[QueryFailureCase] = [
    QueryFailureCase(
        name="orchestrator_http_error_is_a_warning",
        error=httpx.ConnectError("The orchestrator does not answer"),
        log_level=logging.WARNING,
        log_message=ORCHESTRATOR_WARNING,
        traceback=None,
    ),
    QueryFailureCase(
        name="orchestrator_connection_error_is_a_warning",
        error=ConnectionRefusedError("The orchestrator does not answer"),
        log_level=logging.WARNING,
        log_message=ORCHESTRATOR_WARNING,
        traceback=None,
    ),
    QueryFailureCase(
        name="code_error_is_an_error_with_its_traceback",
        error=TypeError("has_queued_run() got an unexpected keyword argument"),
        log_level=logging.ERROR,
        log_message="The delivery recovery check of repository net-repo failed; the next cycle checks again.",
        traceback=TypeError,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in QUERY_FAILURE_CASES])
async def test_a_query_that_raises_submits_nothing_and_leaves_the_progress_time(
    check_rig: CheckRig, case: QueryFailureCase, caplog: pytest.LogCaptureFixture
) -> None:
    runs = FailingDeliveryRunQuery(error=case.error)
    check = DeliveryRecoveryCheck(
        state=check_rig.state,
        workflow=check_rig.workflow,
        runs=runs,
        lock_registry=check_rig.lock_registry,
        clock=FixedClock(now=CHECK_NOW),
        context=RECOVERY_CONTEXT,
    )
    check_rig.state.intents[REPOSITORY.id] = STALE_INTENT

    with caplog.at_level(logging.WARNING, logger=RUN_LOGGER):
        submitted = await check.run(repository=REPOSITORY)

    assert submitted is False
    assert runs.asked == [REPOSITORY.id]
    assert check_rig.workflow.submit_calls == []
    assert check_rig.state.calls == ["read"]
    assert check_rig.state.intents[REPOSITORY.id] == STALE_INTENT
    assert [
        (record.levelno, record.getMessage(), record.exc_info[0] if record.exc_info else None)
        for record in caplog.records
        if record.name == RUN_LOGGER
    ] == [(case.log_level, case.log_message, case.traceback)]


@dataclass
class CheckFailureCase:
    name: str
    failing_call: str
    """`read` or `touch` of the state, or `submit` of the workflow."""
    submits: bool
    state_calls: list[str]
    error_log: str


CHECK_FAILURE_CASES: list[CheckFailureCase] = [
    CheckFailureCase(
        name="failed_state_read_submits_nothing",
        failing_call="read",
        submits=False,
        state_calls=["read"],
        error_log="The delivery recovery check of repository net-repo failed; the next cycle checks again.",
    ),
    CheckFailureCase(
        name="failed_submission_leaves_the_progress_time",
        failing_call="submit",
        submits=False,
        state_calls=["read"],
        error_log="The delivery recovery check of repository net-repo failed; the next cycle checks again.",
    ),
    CheckFailureCase(
        name="failed_touch_keeps_the_submission",
        failing_call="touch",
        submits=True,
        state_calls=["read", "touch"],
        error_log="Could not move the progress time of the delivery of repository net-repo.",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CHECK_FAILURE_CASES])
async def test_the_recovery_check_never_raises(
    check_rig: CheckRig, case: CheckFailureCase, caplog: pytest.LogCaptureFixture
) -> None:
    check_rig.state.intents[REPOSITORY.id] = STALE_INTENT
    error = DatabaseError(message=DATABASE_DOWN)
    if case.failing_call == "submit":
        check_rig.workflow.failures.append(error)
    else:
        check_rig.state.failures[case.failing_call] = [error]

    with caplog.at_level(logging.ERROR, logger=RUN_LOGGER):
        submitted = await run_check(check_rig)

    assert submitted is case.submits
    assert check_rig.workflow.submit_calls == ([EXPECTED_SUBMISSION] if case.submits else [])
    assert check_rig.state.calls == case.state_calls
    assert check_rig.state.intents[REPOSITORY.id] == STALE_INTENT
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR] == [case.error_log]
