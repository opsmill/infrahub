from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import ServerNotReachableError

from infrahub.core.constants import FullRegenerationReason, RepositoryDeliveryFailureCause, RepositoryDeliveryStatus
from infrahub.exceptions import (
    DatabaseError,
    DeliveryQueueChangedError,
    DeliveryStateUnavailableError,
    RepositoryConnectionError,
    RepositoryCredentialsError,
    ValidationError,
)
from infrahub.git.writeback.models import (
    AbandonmentRecord,
    Actor,
    DeliveryAttemptResult,
    DeliveryFailure,
    DeliveryOutcome,
    HeldItem,
    HeldRegeneration,
    HeldWiden,
    PendingMerge,
    ReleaseLease,
)
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.service import RepositoryWritebackService, RetryableDeliveryError
from infrahub.lock import InfrahubLockRegistry
from tests.unit.git.writeback.fakes import (
    FixedClock,
    InMemoryDeliveryGit,
    InMemoryDeliveryState,
    RecordingRegenerationReleaser,
    Release,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from infrahub.exceptions import RepositoryError
    from infrahub.git.writeback.models import WritebackIntent
    from infrahub.lock import InfrahubLock

REPOSITORY = RepositoryRef(id="repository-1", name="net-repo", destination_git_branch="main")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
RUN_LOGGER = "infrahub.tasks"

TRUNK = "a" * 40
"""The head of the remote destination, and the commit that Infrahub records, before each test."""
FEATURE = "b" * 40
OTHER = "c" * 40
UPSTREAM = "d" * 40
"""A commit that another client pushed onto the trunk of the remote destination."""
REWRITE = "e" * 40
"""A commit with no parent, which replaced the history of a remote branch."""
FORCED = "f" * 40
"""A commit on the trunk that replaced the feature commit on the remote branch."""
MERGED = "9" * 40
"""A commit that merged the feature and the other commit on the remote destination."""

CONNECTION_MESSAGE = "Unable to clone the repository net-repo, please check the address and the credential"


class WorkerStoppedError(BaseException):
    """Stops the attempt where a crash of the worker would, so that nothing in the attempt handles it."""


class SteppedGit(InMemoryDeliveryGit):
    """Runs the action that a test sets for a step, right before the step."""

    def __init__(self, *, destination_git_branch: str, head: str) -> None:
        super().__init__(destination_git_branch=destination_git_branch, head=head)
        self.before: dict[str, Callable[[], Awaitable[None]]] = {}

    async def push(self) -> None:
        await self._run_before(step="push")
        await super().push()

    async def record(self, *, commit: str) -> None:
        await self._run_before(step="record")
        await super().record(commit=commit)

    async def import_at(self, *, commit: str) -> None:
        await self._run_before(step="import_at")
        await super().import_at(commit=commit)

    async def _run_before(self, *, step: str) -> None:
        action = self.before.get(step)
        if action is not None:
            await action()


class SteppedReleaser(RecordingRegenerationReleaser):
    """Runs the action that a test sets before each release."""

    def __init__(self) -> None:
        super().__init__()
        self.before: Callable[[], Awaitable[None]] | None = None

    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None:
        if self.before is not None:
            await self.before()
        await super().release(repository_id=repository_id, held=held, renew=renew)


class SettleObservingState(InMemoryDeliveryState):
    """Records whether the repository lock is held at each settle of a delivery."""

    def __init__(self, *, clock: FixedClock, repository_names: Mapping[str, str], lock: InfrahubLock) -> None:
        super().__init__(clock=clock, repository_names=repository_names)
        self.lock = lock
        self.settled_under_lock: list[bool] = []

    async def settle_delivery(
        self, *, repository_id: str, snapshot: WritebackIntent, delivered_commit: str | None
    ) -> ReleaseLease | None:
        self.settled_under_lock.append(await self.lock.locked())
        return await super().settle_delivery(
            repository_id=repository_id, snapshot=snapshot, delivered_commit=delivered_commit
        )


@dataclass
class Rig:
    clock: FixedClock
    state: SettleObservingState
    git: SteppedGit
    releaser: SteppedReleaser
    lock: InfrahubLock
    service: RepositoryWritebackService

    @property
    def intent(self) -> WritebackIntent:
        return self.state.intents[REPOSITORY.id]

    async def queue(self, *entries: PendingMerge) -> None:
        for entry in entries:
            await self.state.enqueue(repository_id=REPOSITORY.id, entry=entry, widen=False)

    async def hold(self, *definition_ids: str) -> None:
        await self.state.hold(
            repository_id=REPOSITORY.id,
            held=HeldRegeneration(
                artifact_definitions=tuple(HeldItem(id=definition_id, hold_seq=0) for definition_id in definition_ids)
            ),
        )

    async def deliver(self, *, final_attempt: bool = False, entry: PendingMerge | None = None) -> DeliveryAttemptResult:
        return await self.service.deliver(final_attempt=final_attempt, manual=False, entry=entry)


def _merge(
    *,
    entry_id: str = "merge-1",
    source_branch: str = "add-vlan",
    source_git_branch: str = "feature",
    source_commit: str = FEATURE,
    delete_source_git_branch: bool = False,
) -> PendingMerge:
    return PendingMerge(
        entry_id=entry_id,
        source_branch=source_branch,
        source_git_branch=source_git_branch,
        source_commit=source_commit,
        merged_at=NOW,
        delete_source_git_branch=delete_source_git_branch,
    )


OTHER_MERGE = _merge(entry_id="merge-2", source_branch="add-vrf", source_git_branch="other", source_commit=OTHER)


def _held(*items: HeldItem) -> HeldRegeneration:
    return HeldRegeneration(artifact_definitions=items)


@pytest.fixture
def rig() -> Rig:
    clock = FixedClock(now=NOW)
    lock_registry = InfrahubLockRegistry(local_only=True)
    lock = lock_registry.get(name=REPOSITORY.name, namespace="repository")
    state = SettleObservingState(clock=clock, repository_names={REPOSITORY.id: REPOSITORY.name}, lock=lock)
    git = SteppedGit(destination_git_branch=REPOSITORY.destination_git_branch, head=TRUNK)
    for commit in (FEATURE, OTHER, UPSTREAM, FORCED):
        git.add_commit(commit=commit, parents=(TRUNK,))
    git.add_commit(commit=REWRITE, parents=())
    git.add_commit(commit=MERGED, parents=(FEATURE, OTHER))
    git.remote_heads.update({"main": TRUNK, "feature": FEATURE, "other": OTHER})
    releaser = SteppedReleaser()
    service = RepositoryWritebackService(
        repository=REPOSITORY, state=state, git=git, releaser=releaser, lock_registry=lock_registry, clock=clock
    )
    return Rig(clock=clock, state=state, git=git, releaser=releaser, lock=lock, service=service)


async def test_nothing_pending_does_nothing(rig: Rig) -> None:
    result = await rig.deliver()

    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.NOTHING_PENDING)
    assert rig.state.calls == ["start_attempt"]
    assert rig.git.calls == []
    assert rig.releaser.releases == []


async def test_entry_is_queued_before_the_snapshot_and_delivered(rig: Rig) -> None:
    entry = _merge()

    result = await rig.deliver(entry=entry)

    delivered = f"{TRUNK}+{FEATURE}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=delivered)
    assert rig.state.calls == [
        "enqueue",
        "start_attempt",
        "progress",
        "progress",
        "progress",
        "settle_delivery",
        "renew_lease",
        "clear_released",
    ]
    assert rig.git.calls == [
        "fetch",
        "remote_head",
        "recorded_commit",
        "is_ancestor",
        "is_ancestor",
        "remote_head",
        "is_ancestor",
        "replay",
        "push",
        "record",
        "broadcast",
    ]
    assert rig.git.pushed == [delivered]
    assert rig.git.recorded == [delivered]
    assert rig.git.imported == []
    assert rig.releaser.releases == [
        Release(
            repository_id=REPOSITORY.id,
            held=HeldRegeneration(
                widen=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=1)
            ),
        )
    ]
    assert rig.intent.queue.entries == ()
    assert rig.intent.queue.removed_entry_ids == ("merge-1",)
    assert rig.intent.status == RepositoryDeliveryStatus.NONE
    assert rig.intent.last_delivered_commit == delivered
    assert rig.intent.held == HeldRegeneration(next_hold_seq=2)


async def test_every_pending_merge_is_replayed_in_order_and_pushed_once(rig: Rig) -> None:
    await rig.queue(_merge(), OTHER_MERGE)

    result = await rig.deliver()

    delivered = f"{TRUNK}+{FEATURE}+{OTHER}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=delivered)
    assert rig.git.pushed == [delivered]
    assert rig.git.recorded == [delivered]
    assert rig.intent.queue.entries == ()
    assert rig.intent.queue.removed_entry_ids == ("merge-1", "merge-2")
    assert rig.intent.last_delivered_commit == delivered


async def test_failed_enqueue_is_retried_before_the_final_attempt(rig: Rig) -> None:
    rig.state.failures["enqueue"] = [DatabaseError(message="Unable to connect to the database")]
    before = rig.intent

    with pytest.raises(RetryableDeliveryError, match=r"^Unable to connect to the database$") as raised:
        await rig.deliver(entry=_merge())

    assert raised.value.failure == DeliveryFailure(
        cause=None, retryable=True, message="Unable to connect to the database"
    )
    assert rig.state.calls == ["enqueue"]
    assert rig.git.calls == []
    assert rig.intent == before


async def test_failed_enqueue_on_the_final_attempt_fails_and_names_the_merge(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    rig.state.failures["enqueue"] = [DatabaseError(message="Unable to connect to the database")]
    before = rig.intent

    with caplog.at_level(logging.ERROR, logger=RUN_LOGGER):
        result = await rig.deliver(final_attempt=True, entry=_merge())

    assert result == DeliveryAttemptResult(
        outcome=DeliveryOutcome.FAILED,
        failure=DeliveryFailure(cause=None, retryable=True, message="Unable to connect to the database"),
    )
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR] == [
        f"The merge of branch add-vlan at commit {FEATURE} was not queued for repository net-repo after the last "
        "attempt; deliver it by hand."
    ]
    assert rig.state.calls == ["enqueue"]
    assert rig.git.calls == []
    assert rig.intent == before


async def test_unavailable_delivery_state_is_retryable(rig: Rig) -> None:
    rig.state.failures["start_attempt"] = [
        DeliveryStateUnavailableError(repository_id=REPOSITORY.id, acquire_seconds=10)
    ]

    with pytest.raises(
        RetryableDeliveryError,
        match=(
            r"^The lock of the delivery state of repository repository-1 was not acquired within 10 seconds; "
            r"try again\.$"
        ),
    ):
        await rig.deliver(final_attempt=True)

    assert await rig.lock.locked() is False


async def test_every_entry_that_the_remote_holds_is_observed_and_its_head_recorded(rig: Rig) -> None:
    await rig.queue(_merge(), OTHER_MERGE)
    rig.git.remote_heads["main"] = MERGED

    result = await rig.deliver()

    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.OBSERVED, commit=MERGED)
    assert rig.git.pushed == []
    assert rig.git.head == MERGED
    assert rig.git.recorded == [MERGED]
    assert rig.git.imported == [MERGED]
    assert rig.intent.queue.entries == ()
    assert rig.intent.queue.import_owed_commit is None
    assert rig.intent.last_delivered_commit is None
    assert rig.intent.status == RepositoryDeliveryStatus.NONE


@dataclass
class RefusalCase:
    name: str
    remote_heads: dict[str, str]
    cause: RepositoryDeliveryFailureCause
    message: str


REFUSAL_CASES: list[RefusalCase] = [
    RefusalCase(
        name="destination_rewritten",
        remote_heads={"main": REWRITE, "feature": FEATURE},
        cause=RepositoryDeliveryFailureCause.DESTINATION_REWRITTEN,
        message=(
            f"The remote branch main of repository net-repo is at {REWRITE}, which does not contain the commit "
            f"{TRUNK} that Infrahub records, so nothing was pushed."
        ),
    ),
    RefusalCase(
        name="destination_missing",
        remote_heads={"feature": FEATURE},
        cause=RepositoryDeliveryFailureCause.DESTINATION_REWRITTEN,
        message="The remote of repository net-repo has no branch main, so nothing was pushed.",
    ),
    RefusalCase(
        name="source_branch_missing",
        remote_heads={"main": TRUNK},
        cause=RepositoryDeliveryFailureCause.SOURCE_DISCARDED,
        message=(
            f"The remote of repository net-repo has no branch feature, which held the commit {FEATURE} of the "
            "merge merge-1 of branch add-vlan, so nothing was pushed."
        ),
    ),
    RefusalCase(
        name="source_commit_discarded",
        remote_heads={"main": TRUNK, "feature": FORCED},
        cause=RepositoryDeliveryFailureCause.SOURCE_DISCARDED,
        message=(
            f"The remote branch feature of repository net-repo is at {FORCED}, which does not contain the commit "
            f"{FEATURE} of the merge merge-1 of branch add-vlan, so nothing was pushed."
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSAL_CASES])
async def test_a_replay_that_would_restore_discarded_commits_is_refused(rig: Rig, case: RefusalCase) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.remote_heads.clear()
    rig.git.remote_heads.update(case.remote_heads)

    result = await rig.deliver()

    failure = DeliveryFailure(cause=case.cause, retryable=False, message=case.message)
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.UNREPLAYABLE, failure=failure)
    assert "replay" not in rig.git.calls
    assert rig.git.pushed == []
    assert rig.git.recorded == []
    assert rig.intent.queue.entries == (entry,)
    assert rig.intent.status == RepositoryDeliveryStatus.ACTION_REQUIRED
    assert rig.intent.cause == case.cause
    assert rig.intent.error == case.message


async def test_no_recorded_commit_skips_the_destination_check_and_owes_an_import(rig: Rig) -> None:
    await rig.queue(_merge())
    rig.git.graph_commit = None
    rig.git.remote_heads["main"] = UPSTREAM

    result = await rig.deliver()

    delivered = f"{UPSTREAM}+{FEATURE}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=delivered)
    assert rig.git.pushed == [delivered]
    assert rig.git.imported == [delivered]


async def test_replay_conflict_resets_to_the_recorded_commit_and_names_the_merge(rig: Rig) -> None:
    conflicting = _merge()
    await rig.queue(OTHER_MERGE, conflicting)
    rig.git.remote_heads["main"] = UPSTREAM
    rig.git.conflicting_commits.add(FEATURE)

    result = await rig.deliver()

    message = (
        f"The merge merge-1 of branch add-vlan at commit {FEATURE} conflicts with the remote branch main of "
        f"repository net-repo at {UPSTREAM}, so nothing was pushed."
    )
    assert result == DeliveryAttemptResult(
        outcome=DeliveryOutcome.UNREPLAYABLE,
        failure=DeliveryFailure(cause=RepositoryDeliveryFailureCause.REPLAY_CONFLICT, retryable=False, message=message),
    )
    assert rig.git.calls[-2:] == ["replay", "reset"]
    assert rig.git.head == TRUNK
    assert rig.git.pushed == []
    assert rig.intent.queue.entries == (OTHER_MERGE, conflicting)
    assert rig.intent.status == RepositoryDeliveryStatus.ACTION_REQUIRED
    assert rig.intent.error == message


@dataclass
class PushFailureCase:
    name: str
    error: RepositoryError
    final_attempt: bool
    retried: bool
    failure: DeliveryFailure
    status: RepositoryDeliveryStatus


PUSH_FAILURE_CASES: list[PushFailureCase] = [
    PushFailureCase(
        name="unreachable_remote_is_retried_before_the_final_attempt",
        error=RepositoryConnectionError(identifier="net-repo"),
        final_attempt=False,
        retried=True,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=CONNECTION_MESSAGE
        ),
        status=RepositoryDeliveryStatus.PENDING,
    ),
    PushFailureCase(
        name="unreachable_remote_on_the_final_attempt_fails",
        error=RepositoryConnectionError(identifier="net-repo"),
        final_attempt=True,
        retried=False,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=CONNECTION_MESSAGE
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
    ),
    PushFailureCase(
        name="refused_credentials_fail_at_once",
        error=RepositoryCredentialsError(identifier="net-repo"),
        final_attempt=False,
        retried=False,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CREDENTIALS,
            retryable=False,
            message="Authentication failed for net-repo, please validate the credentials.",
        ),
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in PUSH_FAILURE_CASES])
async def test_push_failure_resets_to_the_recorded_commit_and_records_the_cause(
    rig: Rig, case: PushFailureCase
) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.failures["push"] = [case.error]

    if case.retried:
        with pytest.raises(RetryableDeliveryError, match=rf"^{re.escape(case.failure.message)}$") as raised:
            await rig.deliver(final_attempt=case.final_attempt)
        assert raised.value.failure == case.failure
    else:
        result = await rig.deliver(final_attempt=case.final_attempt)
        assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.FAILED, failure=case.failure)

    assert rig.git.head == TRUNK
    assert rig.git.recorded == []
    assert rig.intent.queue.entries == (entry,)
    assert rig.intent.status == case.status
    assert rig.intent.cause == case.failure.cause
    assert rig.intent.error == case.failure.message


async def test_failed_read_of_the_recorded_commit_is_retried_as_a_failed_record(rig: Rig) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.failures["recorded_commit"] = [ServerNotReachableError(address="http://infrahub-server:8000")]
    message = "The record step of the delivery failed with ServerNotReachableError."

    with pytest.raises(RetryableDeliveryError, match=rf"^{re.escape(message)}$") as raised:
        await rig.deliver()

    assert raised.value.failure == DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.RECORD_FAILED, retryable=True, message=message
    )
    assert rig.git.calls == ["fetch", "remote_head", "recorded_commit"]
    assert rig.intent.queue.entries == (entry,)
    assert rig.intent.status == RepositoryDeliveryStatus.PENDING
    assert rig.intent.cause == RepositoryDeliveryFailureCause.RECORD_FAILED
    assert rig.intent.error == message


@dataclass
class UnrecordedFailureCase:
    name: str
    git_failures: dict[str, list[Exception]]
    conflicting_commits: frozenset[str]
    error_line: str


UNRECORDED_FAILURE_CASES: list[UnrecordedFailureCase] = [
    UnrecordedFailureCase(
        name="refused_push",
        git_failures={"push": [RepositoryCredentialsError(identifier="net-repo")]},
        conflicting_commits=frozenset(),
        error_line=(
            "The push step of the delivery to repository net-repo failed: Authentication failed for net-repo, "
            "please validate the credentials."
        ),
    ),
    UnrecordedFailureCase(
        name="replay_conflict",
        git_failures={},
        conflicting_commits=frozenset({FEATURE}),
        error_line=(
            f"The delivery to repository net-repo was refused: The merge merge-1 of branch add-vlan at commit "
            f"{FEATURE} conflicts with the remote branch main of repository net-repo at {TRUNK}, so nothing was "
            "pushed."
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in UNRECORDED_FAILURE_CASES])
async def test_failure_is_logged_before_a_failed_record_of_it_stops_the_attempt(
    rig: Rig, case: UnrecordedFailureCase, caplog: pytest.LogCaptureFixture
) -> None:
    await rig.queue(_merge())
    rig.git.failures.update({method: list(errors) for method, errors in case.git_failures.items()})
    rig.git.conflicting_commits.update(case.conflicting_commits)
    rig.state.failures["record_failure"] = [
        DeliveryStateUnavailableError(repository_id=REPOSITORY.id, acquire_seconds=10)
    ]

    with (
        caplog.at_level(logging.ERROR, logger=RUN_LOGGER),
        pytest.raises(
            RetryableDeliveryError,
            match=(
                r"^The lock of the delivery state of repository repository-1 was not acquired within 10 seconds; "
                r"try again\.$"
            ),
        ),
    ):
        await rig.deliver()

    assert [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR] == [case.error_line]
    assert rig.state.calls[-1] == "record_failure"


async def test_import_is_owed_before_the_commit_is_recorded(rig: Rig) -> None:
    await rig.queue(_merge())
    rig.git.remote_heads["main"] = UPSTREAM
    owed_at_record: list[str | None] = []

    async def read_owed_import() -> None:
        owed_at_record.append(rig.intent.queue.import_owed_commit)

    rig.git.before["record"] = read_owed_import

    result = await rig.deliver()

    delivered = f"{UPSTREAM}+{FEATURE}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=delivered)
    assert owed_at_record == [delivered]
    assert rig.git.imported == [delivered]
    assert rig.intent.queue.import_owed_commit is None


async def test_crash_between_the_owed_import_and_the_record_leaves_the_import_to_the_next_attempt(rig: Rig) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.remote_heads["main"] = UPSTREAM
    rig.git.failures["record"] = [WorkerStoppedError()]
    delivered = f"{UPSTREAM}+{FEATURE}"

    with pytest.raises(WorkerStoppedError):
        await rig.deliver()

    assert rig.git.pushed == [delivered]
    assert rig.git.recorded == []
    assert rig.intent.queue.import_owed_commit == delivered
    assert rig.intent.queue.entries == (entry,)
    assert await rig.lock.locked() is False

    result = await rig.deliver()

    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.OBSERVED, commit=delivered)
    assert rig.git.recorded == [delivered]
    assert rig.git.imported == [delivered]
    assert rig.intent.queue.import_owed_commit is None
    assert rig.intent.queue.entries == ()


async def test_failed_record_resets_the_worktree_and_keeps_the_pushed_merge_queued(rig: Rig) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.remote_heads["main"] = UPSTREAM
    rig.git.failures["record"] = [DatabaseError(message="Unable to connect to the database")]

    result = await rig.deliver(final_attempt=True)

    delivered = f"{UPSTREAM}+{FEATURE}"
    failure = DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.RECORD_FAILED, retryable=True, message="Unable to connect to the database"
    )
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.FAILED, commit=delivered, failure=failure)
    assert rig.git.calls[-2:] == ["record", "reset"]
    assert rig.git.head == TRUNK
    assert rig.git.pushed == [delivered]
    assert rig.git.recorded == []
    assert "settle_delivery" not in rig.state.calls
    assert rig.intent.queue.entries == (entry,)
    assert rig.intent.cause == RepositoryDeliveryFailureCause.RECORD_FAILED


@dataclass
class ImportCase:
    name: str
    remote_head: str
    owed_before: str | None
    imported: list[str]


IMPORT_CASES: list[ImportCase] = [
    ImportCase(name="remote_did_not_move", remote_head=TRUNK, owed_before=None, imported=[]),
    ImportCase(name="remote_advanced", remote_head=UPSTREAM, owed_before=None, imported=[f"{UPSTREAM}+{FEATURE}"]),
    ImportCase(name="import_already_owed", remote_head=TRUNK, owed_before=TRUNK, imported=[f"{TRUNK}+{FEATURE}"]),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in IMPORT_CASES])
async def test_import_runs_only_when_owed(rig: Rig, case: ImportCase) -> None:
    await rig.queue(_merge())
    if case.owed_before is not None:
        await rig.state.owe_import(repository_id=REPOSITORY.id, commit=case.owed_before)
    rig.git.remote_heads["main"] = case.remote_head

    result = await rig.deliver()

    assert result.outcome == DeliveryOutcome.DELIVERED
    assert rig.git.imported == case.imported
    assert rig.intent.queue.import_owed_commit is None


async def test_queue_that_grew_during_the_import_keeps_the_import_owed(rig: Rig) -> None:
    await rig.queue(_merge())
    rig.git.remote_heads["main"] = UPSTREAM

    async def merge_other_branch() -> None:
        await rig.queue(OTHER_MERGE)

    rig.git.before["import_at"] = merge_other_branch

    result = await rig.deliver()

    delivered = f"{UPSTREAM}+{FEATURE}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=delivered)
    assert rig.git.imported == [delivered]
    assert rig.intent.queue.import_owed_commit == delivered
    assert rig.intent.queue.entries == (OTHER_MERGE,)
    assert rig.intent.status == RepositoryDeliveryStatus.PENDING


@dataclass
class ImportFailureCase:
    name: str
    error: Exception
    final_attempt: bool
    failure: DeliveryFailure


IMPORT_FAILURE_CASES: list[ImportFailureCase] = [
    ImportFailureCase(
        name="interrupted_import_on_the_final_attempt",
        error=DatabaseError(message="Unable to connect to the database"),
        final_attempt=True,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED,
            retryable=True,
            message="Unable to connect to the database",
        ),
    ),
    ImportFailureCase(
        name="invalid_content_before_the_final_attempt",
        error=ValidationError(input_value="The artifact definition net-config has no target group."),
        final_attempt=False,
        failure=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_FAILED,
            retryable=False,
            message="The artifact definition net-config has no target group.",
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in IMPORT_FAILURE_CASES])
async def test_final_import_failure_keeps_the_import_owed_and_the_merge_queued(
    rig: Rig, case: ImportFailureCase
) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.remote_heads["main"] = UPSTREAM
    rig.git.failures["import_at"] = [case.error]

    result = await rig.deliver(final_attempt=case.final_attempt)

    delivered = f"{UPSTREAM}+{FEATURE}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.FAILED, commit=delivered, failure=case.failure)
    assert rig.git.pushed == [delivered]
    assert rig.git.recorded == [delivered]
    assert rig.git.imported == []
    assert "settle_delivery" not in rig.state.calls
    assert rig.intent.queue.import_owed_commit == delivered
    assert rig.intent.queue.entries == (entry,)
    assert rig.intent.status == RepositoryDeliveryStatus.ACTION_REQUIRED
    assert rig.intent.cause == case.failure.cause
    assert rig.intent.error == case.failure.message


async def test_failed_broadcast_still_delivers_and_names_the_repository(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    await rig.queue(_merge())
    rig.git.failures["broadcast"] = [RuntimeError("The message bus is not reachable.")]

    with caplog.at_level(logging.WARNING, logger=RUN_LOGGER):
        result = await rig.deliver()

    delivered = f"{TRUNK}+{FEATURE}"
    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.DELIVERED, commit=delivered)
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING] == [
        f"Failed to ask the workers to fetch {delivered} for repository net-repo."
    ]
    assert rig.git.broadcasts == []
    assert rig.intent.queue.entries == ()
    assert rig.intent.status == RepositoryDeliveryStatus.NONE
    assert rig.intent.last_delivered_commit == delivered


async def test_settle_runs_under_the_lock_and_leases_only_holds_up_to_the_snapshot(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")

    async def merge_and_hold_during_the_push() -> None:
        await rig.queue(OTHER_MERGE)
        await rig.hold("definition-2")

    rig.git.before["push"] = merge_and_hold_during_the_push

    await rig.deliver()

    assert rig.state.settled_under_lock == [True]
    assert rig.releaser.releases == [
        Release(repository_id=REPOSITORY.id, held=_held(HeldItem(id="definition-1", hold_seq=1)))
    ]
    assert rig.intent.held.artifact_definitions == (HeldItem(id="definition-2", hold_seq=2),)
    assert rig.intent.held.release_leases == ()
    assert rig.intent.queue.entries == (OTHER_MERGE,)


async def test_release_runs_after_the_lock_is_released_and_renews_the_lease(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    locked_at_release: list[bool] = []

    async def read_lock() -> None:
        locked_at_release.append(await rig.lock.locked())

    rig.releaser.before = read_lock

    await rig.deliver()

    assert locked_at_release == [False]
    assert rig.state.calls[-3:] == ["settle_delivery", "renew_lease", "clear_released"]


async def test_clear_removes_only_the_items_of_the_lease_window(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")

    async def hold_again_during_the_release() -> None:
        await rig.queue(OTHER_MERGE)
        await rig.hold("definition-1")

    rig.releaser.before = hold_again_during_the_release

    await rig.deliver()

    assert rig.releaser.releases == [
        Release(repository_id=REPOSITORY.id, held=_held(HeldItem(id="definition-1", hold_seq=1)))
    ]
    assert rig.intent.held.artifact_definitions == (HeldItem(id="definition-1", hold_seq=2),)
    assert rig.intent.held.release_leases == ()


async def test_held_only_run_under_a_live_lease_does_nothing(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    await rig.state.settle_delivery(repository_id=REPOSITORY.id, snapshot=rig.intent, delivered_commit=None)
    before = rig.intent.held
    rig.state.calls.clear()

    result = await rig.deliver()

    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.NOTHING_PENDING)
    assert rig.state.calls == ["start_attempt"]
    assert rig.git.calls == []
    assert rig.releaser.releases == []
    assert rig.intent.held == before


async def test_failed_release_is_released_again_by_the_retry_under_a_new_lease(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    rig.releaser.failures.append(RuntimeError("dispatch failed"))
    leases_at_release: list[tuple[str, ...]] = []

    async def read_leases() -> None:
        leases_at_release.append(tuple(lease.lease_id for lease in rig.intent.held.release_leases))

    rig.releaser.before = read_leases

    with pytest.raises(RetryableDeliveryError, match=r"^The release step of the delivery failed with RuntimeError\.$"):
        await rig.deliver()

    held = HeldItem(id="definition-1", hold_seq=1)
    assert rig.state.calls[-2:] == ["expire_lease", "record_failure"]
    assert rig.intent.queue.entries == ()
    assert rig.intent.held.artifact_definitions == (held,)
    assert rig.intent.held.release_leases == (
        ReleaseLease(lease_id="lease-1", expires_at=NOW, artifact_definitions=(held,)),
    )

    result = await rig.deliver()

    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.RELEASED)
    assert leases_at_release == [("lease-1",), ("lease-2",)]
    assert rig.releaser.releases == [Release(repository_id=REPOSITORY.id, held=_held(held))]
    assert rig.intent.held.artifact_definitions == ()
    assert rig.intent.held.release_leases == ()


async def test_failed_release_on_the_final_attempt_fails_and_keeps_the_items_held(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    rig.releaser.failures.append(RuntimeError("dispatch failed"))

    with caplog.at_level(logging.ERROR, logger=RUN_LOGGER):
        result = await rig.deliver(final_attempt=True)

    message = "The release step of the delivery failed with RuntimeError."
    held = HeldItem(id="definition-1", hold_seq=1)
    assert result == DeliveryAttemptResult(
        outcome=DeliveryOutcome.FAILED,
        commit=f"{TRUNK}+{FEATURE}",
        failure=DeliveryFailure(cause=None, retryable=True, message=message),
    )
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR] == [
        f"The release step of the delivery to repository net-repo failed: {message}"
    ]
    assert rig.intent.status == RepositoryDeliveryStatus.NONE
    assert rig.intent.held.artifact_definitions == (held,)
    assert rig.intent.held.release_leases == (
        ReleaseLease(lease_id="lease-1", expires_at=NOW, artifact_definitions=(held,)),
    )


async def test_failed_release_on_the_final_attempt_asks_for_no_action_when_a_merge_joined_after_the_settle(
    rig: Rig,
) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    rig.releaser.failures.append(RuntimeError("dispatch failed"))

    async def merge_other_branch() -> None:
        await rig.queue(OTHER_MERGE)

    rig.releaser.before = merge_other_branch

    result = await rig.deliver(final_attempt=True)

    message = "The release step of the delivery failed with RuntimeError."
    assert result == DeliveryAttemptResult(
        outcome=DeliveryOutcome.FAILED,
        commit=f"{TRUNK}+{FEATURE}",
        failure=DeliveryFailure(cause=None, retryable=True, message=message),
    )
    assert rig.intent.queue.entries == (OTHER_MERGE,)
    assert rig.intent.status == RepositoryDeliveryStatus.PENDING
    assert rig.intent.error == message


@dataclass
class SourceBranchCase:
    name: str
    deleted: list[str]
    joining: PendingMerge | None = None
    """A merge that joins the queue during the attempt."""
    deletion_errors: list[Exception] = field(default_factory=list)


SOURCE_BRANCH_CASES: list[SourceBranchCase] = [
    SourceBranchCase(name="no_queued_merge_comes_from_the_branch", deleted=["feature"]),
    SourceBranchCase(
        name="a_merge_that_joined_comes_from_the_branch",
        deleted=[],
        joining=_merge(entry_id="merge-3", source_branch="add-vlan-again", source_commit=OTHER),
    ),
    SourceBranchCase(
        name="a_failed_deletion_keeps_the_branch",
        deleted=[],
        deletion_errors=[RepositoryConnectionError(identifier="net-repo")],
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SOURCE_BRANCH_CASES])
async def test_delivered_source_branch_is_deleted_when_no_queued_merge_needs_it(
    rig: Rig, case: SourceBranchCase
) -> None:
    await rig.queue(_merge(delete_source_git_branch=True))
    rig.git.failures["delete_remote_branch"] = list(case.deletion_errors)
    joining = case.joining

    async def merge_during_the_push() -> None:
        if joining is not None:
            await rig.queue(joining)

    rig.git.before["push"] = merge_during_the_push

    result = await rig.deliver()

    assert result.outcome == DeliveryOutcome.DELIVERED
    assert rig.git.deleted_branches == case.deleted
    assert rig.git.notified_branches == case.deleted


async def test_abandonment_and_deletion_guard_that_wait_for_the_lock_find_the_entries_settled(rig: Rig) -> None:
    await rig.queue(_merge())
    seen_version = rig.intent.queue.version
    pushing = asyncio.Event()
    resume = asyncio.Event()

    async def pause_the_push() -> None:
        pushing.set()
        await resume.wait()

    rig.git.before["push"] = pause_the_push

    async def guard_the_deletion() -> bool:
        async with rig.lock:
            return await rig.state.request_branch_deletion(repository_id=REPOSITORY.id, git_branch="feature")

    async def abandon() -> DeliveryQueueChangedError | None:
        async with rig.lock:
            try:
                await rig.state.abandon(
                    repository_id=REPOSITORY.id,
                    queue_version=seen_version,
                    record=AbandonmentRecord(
                        abandoned_at=NOW,
                        account_id="account-1",
                        account_name="admin",
                        queue_version=seen_version,
                        recorded_commit=TRUNK,
                    ),
                    actor=Actor(account_id="account-1", account_name="admin"),
                )
            except DeliveryQueueChangedError as exc:
                return exc
        return None

    attempt = asyncio.create_task(rig.deliver())
    await asyncio.wait_for(pushing.wait(), timeout=5)
    guard = asyncio.create_task(guard_the_deletion())
    abandonment = asyncio.create_task(abandon())
    for _ in range(5):
        await asyncio.sleep(0)
    assert not guard.done()
    assert not abandonment.done()

    resume.set()
    result = await asyncio.wait_for(attempt, timeout=5)
    flagged = await asyncio.wait_for(guard, timeout=5)
    refusal = await asyncio.wait_for(abandonment, timeout=5)

    assert result.outcome == DeliveryOutcome.DELIVERED
    assert flagged is False
    assert refusal is not None
    assert refusal.message == "The pending pushes of repository net-repo changed since version 1; reload and try again."
    assert rig.intent.last_abandonment is None
