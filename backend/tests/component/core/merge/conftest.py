"""Shared fakes and builders for the merge-failure recovery tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.merge.failure_identifier import MergeFailureIdentifier
from infrahub.core.merge.failure_recoverer import MergeFailureRecoverer
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.registry import registry
from infrahub.core.rollback import GraphRollbacker
from infrahub.locks.cleaner import StaleLockCleaner

if TYPE_CHECKING:
    import pytest

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.component import InfrahubComponent
    from tests.adapters.cache import MemoryCache

# Recovery finds the durably flagged branch directly, so the liveness grace period is irrelevant to
# most tests; those that exercise the MERGING liveness gate override it per-call.
GRACE_PERIOD_SECONDS = 180


def find_logged_event(caplog: pytest.LogCaptureFixture, *, event: str, branch: str) -> dict | None:
    """Return the structured payload of a captured log entry with the given event name and branch.

    Structured logs are captured as the event dict on the record, so the returned mapping carries the
    event's bound fields (worker id, timestamps, ...) for the caller to assert on. Returns ``None`` when
    no matching entry was captured.
    """
    for record in caplog.records:
        message = record.msg
        if isinstance(message, dict) and message.get("event") == event and message.get("branch") == branch:
            return message
    return None


class InMemorySchemaRecoverer(MergeFailureRecoverer):
    """Recoverer that recomputes the schema hash from the in-memory registry instead of the database.

    Loading the schema from the database is a slow round-trip; the recovery logic under test does not
    depend on that round-trip, so the schema is read from the registry to keep these tests fast.
    """

    async def _load_destination_schema(self, branch: Branch) -> SchemaBranch:
        return registry.schema.get_schema_branch(name=branch.name)


class FailAtBranchResetRecoverer(InMemorySchemaRecoverer):
    """Real recoverer that raises while resetting the branch, after the graph rollback has run.

    Reproduces a recovery interrupted after the rollback lands but before the branch is reopened and
    the protection lifted, so the branch stays flagged and protected for a re-run.
    """

    async def _reset_branch(self, branch: Branch) -> None:
        raise RuntimeError("branch reset failed")


class FailAtLockReleaseRecoverer(InMemorySchemaRecoverer):
    """Real recoverer whose merge-lock release fails, before the branch is reopened.

    Reproduces a cache backend that cannot drop the stale lock key. The failure must not be swallowed:
    a held lock blocks every future merge, so recovery must report failure and leave the branch flagged,
    the protection held and the lock in place for a re-run.
    """

    async def _release_merge_lock(self) -> None:
        raise RuntimeError("lock release failed")


def build_identifier(
    db: InfrahubDatabase,
    cache: MemoryCache,
    component: InfrahubComponent,
    default_branch: Branch,
    grace_period_seconds: int = GRACE_PERIOD_SECONDS,
) -> MergeFailureIdentifier:
    return MergeFailureIdentifier(
        db=db,
        cache=cache,
        component=component,
        merge_write_blocker=MergeWriteBlocker(cache=cache),
        default_branch=default_branch,
        grace_period_seconds=grace_period_seconds,
    )


def build_recovery(
    db: InfrahubDatabase,
    cache: MemoryCache,
    component: InfrahubComponent,
    default_branch: Branch,
    grace_period_seconds: int = GRACE_PERIOD_SECONDS,
    recoverer_class: type[MergeFailureRecoverer] = InMemorySchemaRecoverer,
    merge_write_blocker: MergeWriteBlocker | None = None,
) -> MergeFailureRecoverer:
    return recoverer_class(
        db=db,
        merge_write_blocker=merge_write_blocker or MergeWriteBlocker(cache=cache),
        identifier=build_identifier(
            db=db,
            cache=cache,
            component=component,
            default_branch=default_branch,
            grace_period_seconds=grace_period_seconds,
        ),
        default_branch=default_branch,
        cache=cache,
        rollbacker=GraphRollbacker(db=db),
        schema_manager=registry.schema,
        lock_cleaner=StaleLockCleaner(cache=cache, component=component, default_branch_name=default_branch.name),
        diff_locker=DiffLocker(),
    )
