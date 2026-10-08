from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from prefect.client.schemas.objects import TaskRun
from prefect.states import Failed

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
from infrahub.git.models import PushRejectionReason
from infrahub.git.tasks import deliver_pending_merges
from infrahub.git.writeback.models import DeliveryAttemptResult, DeliveryFailure, DeliveryOutcome, PendingMerge
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.runs import is_retryable_delivery_failure, next_retry_delay
from infrahub.git.writeback.service import RepositoryWritebackService, RetryableDeliveryError
from infrahub.lock import InfrahubLockRegistry
from tests.unit.git.writeback.fakes import (
    FixedClock,
    InMemoryDeliveryGit,
    InMemoryDeliveryState,
    RecordingRegenerationReleaser,
)

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
