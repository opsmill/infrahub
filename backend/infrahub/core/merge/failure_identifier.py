from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

from .merge_locker import get_merge_lock_holder_worker_id
from .write_blocker import MergeProtectionState, MergeWriteBlocker

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.component import InfrahubComponent

log = get_logger()


class RecoveryOutcome(Enum):
    NOTHING_TO_RECOVER = "nothing_to_recover"
    DECLINED = "declined"
    RECOVERED = "recovered"
    ORPHANED_CLEARED = "orphaned_cleared"
    FAILED = "failed"


@dataclass(frozen=True)
class RecoveryReport:
    outcome: RecoveryOutcome
    branch: str | None
    proposed_change: str | None
    merge_started_at: str | None


class MergeFailureIdentifier:
    """Act on a merge whose worker died mid-flight.

    ``detect_and_mark`` is a read-side liveness check: a branch stuck in ``MERGING`` whose merge-lock
    holder is no longer a live worker (after a grace period) is flipped to the durable
    ``MERGE_FAILED`` status, and the shared write-protection key is updated so every worker keeps
    rejecting writes to the default branch with the recovery message.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        cache: InfrahubCache,
        component: InfrahubComponent,
        merge_write_blocker: MergeWriteBlocker,
        grace_period_seconds: int,
    ) -> None:
        self.db = db
        self.cache = cache
        self.component = component
        self.merge_write_blocker = merge_write_blocker
        self.grace_period_seconds = grace_period_seconds

    def should_mark_as_failed_merge(
        self,
        *,
        status: BranchStatus,
        lock_holder_worker_id: str | None,
        active_worker_ids: set[str],
        merge_started_at: Timestamp | None,
        now: Timestamp,
    ) -> bool:
        """Decide whether a branch represents a dead merge that must be flagged ``MERGE_FAILED``.

        A merge has failed when all of the following hold:
          - the branch is still ``MERGING`` (it never reached ``MERGED`` or rolled back to ``OPEN``),
          - the global merge lock is *held* (``lock_holder_worker_id is not None``) — a dead worker
            cannot release it, so a genuine failure leaves it held; an absent lock is ambiguous (a
            cache flush during a live merge would look the same) and is deliberately not auto-flagged,
          - the lock holder is not among the live workers (the holder died), and
          - the merge has been running longer than the grace period, which absorbs a transient
            worker-heartbeat write blip so a healthy merge is never mis-flagged.
        """
        if status != BranchStatus.MERGING:
            return False
        if lock_holder_worker_id is None:
            return False
        if lock_holder_worker_id in active_worker_ids:
            return False
        if merge_started_at is None:
            return False
        return merge_started_at.add(seconds=self.grace_period_seconds) < now

    async def scan(self) -> str | None:
        """Detect a dead merge and reconcile the protection key.

        Flip any dead ``MERGING`` branch to ``MERGE_FAILED`` (holding the protection), then
        re-align the shared write-protection key with the durable branch status so it self-heals
        after a restart or cache flush. Returns the branch flagged failed this pass, or ``None``.
        Idempotent.
        """
        flagged = await self._detect_and_mark()
        await self._reconcile_protection_key()
        return flagged

    async def _detect_and_mark(self) -> str | None:
        merging = await Branch.get_list(db=self.db, branch_filters=BranchListFilters(status=BranchStatus.MERGING))
        if not merging:
            return None

        # The liveness signal is the worker holding the global merge lock: a dead holder means a
        # crashed merge.
        lock_holder_worker_id = await get_merge_lock_holder_worker_id(cache=self.cache)
        active_worker_ids = await self._active_worker_ids()
        now = Timestamp()

        for branch in merging:
            merge_started_at = Timestamp(branch.merge_started_at) if branch.merge_started_at else None
            if not self.should_mark_as_failed_merge(
                status=branch.status,
                lock_holder_worker_id=lock_holder_worker_id,
                active_worker_ids=active_worker_ids,
                merge_started_at=merge_started_at,
                now=now,
            ):
                continue

            branch.status = BranchStatus.MERGE_FAILED
            await branch.save(db=self.db)
            registry.branch[branch.name] = branch
            await self.merge_write_blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)
            log.warning(
                "Detected a failed merge; holding write protection until recovery",
                branch=branch.name,
                merge_started_at=branch.merge_started_at,
            )
            return branch.name

        return None

    async def _reconcile_protection_key(self) -> None:
        """Re-align the shared write-protection key with the durable branch status.

        The cache key is the fast signal every worker reads, but it is volatile (a restart or cache
        flush can drop it). The durable ``MERGING``/``MERGE_FAILED`` branch status in the database is
        the source of truth, so this restores the key when it is missing for a protected branch and
        removes it when no branch is protected.
        """
        # At most one branch is protected at a time (merges are serialized by the global lock);
        # MERGE_FAILED takes precedence as the durable, more severe state.
        protected_branches = await Branch.get_list(
            db=self.db,
            branch_filters=BranchListFilters(statuses=[BranchStatus.MERGE_FAILED, BranchStatus.MERGING]),
        )
        protected = next(
            (b for b in protected_branches if b.status == BranchStatus.MERGE_FAILED),
            protected_branches[0] if protected_branches else None,
        )

        protection = await self.merge_write_blocker.get()

        if protected is None:
            if protection is not None:
                await self.merge_write_blocker.delete()
            return

        expected_state = (
            MergeProtectionState.MERGE_FAILED
            if protected.status == BranchStatus.MERGE_FAILED
            else MergeProtectionState.MERGING
        )
        if protection is None or protection.branch != protected.name or protection.state != expected_state:
            await self.merge_write_blocker.set(branch=protected.name, state=expected_state)

    async def _active_worker_ids(self) -> set[str]:
        workers = await self.component.list_workers(branch=registry.default_branch, schema_hash=False)
        return {worker.id for worker in workers if worker.active}


async def scan_for_failed_merges(db: InfrahubDatabase, service: InfrahubServices) -> str | None:
    """Build a ``MergeFailureRecovery`` from the running service and run one detection scan."""
    recovery = MergeFailureIdentifier(
        db=db,
        cache=service.cache,
        component=service.component,
        merge_write_blocker=MergeWriteBlocker(cache=service.cache),
        grace_period_seconds=config.SETTINGS.main.merge_failure_grace_period_seconds,
    )
    return await recovery.scan()
