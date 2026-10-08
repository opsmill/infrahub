from __future__ import annotations

from datetime import UTC, datetime

from prefect import flow

from infrahub.core.constants import RepositoryDeliveryFailureCause
from infrahub.exceptions import RepositoryConnectionError
from infrahub.git.tasks import deliver_pending_merges
from infrahub.git.writeback.models import DeliveryFailure, DeliveryOutcome, PendingMerge
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.service import RepositoryWritebackService
from infrahub.lock import InfrahubLockRegistry
from tests.unit.git.writeback.fakes import (
    FixedClock,
    InMemoryDeliveryGit,
    RecordedFailure,
    RecordingDeliveryState,
    RecordingRegenerationReleaser,
)

REPOSITORY = RepositoryRef(id="repository-1", name="net-repo", destination_git_branch="main")
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
TRUNK = "a" * 40
FEATURE = "b" * 40
ENTRY = PendingMerge(
    entry_id="merge-1", source_branch="add-vlan", source_git_branch="feature", source_commit=FEATURE, merged_at=NOW
)
UNREACHABLE = "The remote net-repo does not answer."


async def test_the_delivery_task_records_when_its_retry_is_due_before_it_waits(prefect_test_fixture: None) -> None:
    clock = FixedClock(now=NOW)
    state = RecordingDeliveryState(clock=clock, repository_names={REPOSITORY.id: REPOSITORY.name})
    git = InMemoryDeliveryGit(destination_git_branch=REPOSITORY.destination_git_branch, head=TRUNK)
    git.add_commit(commit=FEATURE, parents=(TRUNK,))
    git.remote_heads.update({"main": TRUNK, "feature": FEATURE})
    git.failures["push"] = [RepositoryConnectionError(identifier=REPOSITORY.name, message=UNREACHABLE)]
    service = RepositoryWritebackService(
        repository=REPOSITORY,
        state=state,
        git=git,
        releaser=RecordingRegenerationReleaser(),
        lock_registry=InfrahubLockRegistry(local_only=True),
        clock=clock,
    )
    deliver = deliver_pending_merges.with_options(retries=1, retry_delay_seconds=[0.05])

    @flow(name="test-deliver-pending-merges")
    async def run_delivery() -> DeliveryOutcome:
        return await deliver(service=service, manual=False, entry=ENTRY)

    outcome = await run_delivery()

    assert outcome == DeliveryOutcome.DELIVERED
    assert state.recorded_failures == [
        RecordedFailure(
            failure=DeliveryFailure(
                cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=UNREACHABLE
            ),
            final=False,
            retry_due_at=datetime(2026, 10, 8, 12, 0, 0, 50_000, tzinfo=UTC),
        )
    ]
    assert git.pushed == [f"{TRUNK}+{FEATURE}"]
