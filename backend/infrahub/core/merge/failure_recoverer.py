from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreProposedChange
from infrahub.core.query.rollback import RollbackQuery, RollbackScope
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.proposed_change.constants import ProposedChangeState

from .write_blocker import MalformedMergeProtectionError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .failure_identifier import MergeFailureIdentifier
    from .write_blocker import MergeWriteBlocker

log = get_logger()


class RecoveryOutcome(Enum):
    NOTHING_TO_RECOVER = "nothing_to_recover"
    RECOVERABLE = "recoverable"
    RECOVERED = "recovered"
    ORPHANED_CLEARED = "orphaned_cleared"
    FAILED = "failed"


@dataclass(frozen=True)
class RecoveryReport:
    outcome: RecoveryOutcome
    branch: str | None
    proposed_change: str | None
    merge_started_at: str | None


class MergeFailureRecoverer:
    """Reverse a failed branch merge and return the system to a writable state.

    A merge that dies mid-flight leaves the default branch partially merged and write-protected.
    ``recover`` finds that branch, reverses the partial merge with the range rollback, resets any
    associated proposed change and then the branch to ``OPEN``, and lifts the write protection. It
    is idempotent. A run interrupted before the write protection is lifted leaves the branch
    flagged so a re-run re-detects it, re-runs the rollback (a no-op) and finishes the reset.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        merge_write_blocker: MergeWriteBlocker,
        identifier: MergeFailureIdentifier,
        default_branch: Branch,
    ) -> None:
        self.db = db
        self.merge_write_blocker = merge_write_blocker
        self.identifier = identifier
        self.default_branch = default_branch

    async def preview(self, *, force: bool = False, branch_name: str | None = None) -> RecoveryReport:
        """Report whether a failed merge can be recovered, making no changes.

        Read-only: it never lifts write protection or touches a branch. When a recoverable branch is
        found it reports ``RECOVERABLE`` with the branch, its merge start and any associated proposed
        change so an operator can decide; otherwise it reports ``NOTHING_TO_RECOVER``.
        """
        recoverable = await self._find_recoverable(force=force, branch_name=branch_name)
        if recoverable is None:
            return RecoveryReport(
                outcome=RecoveryOutcome.NOTHING_TO_RECOVER, branch=None, proposed_change=None, merge_started_at=None
            )

        branch, proposed_change = recoverable
        return RecoveryReport(
            outcome=RecoveryOutcome.RECOVERABLE,
            branch=branch.name,
            proposed_change=proposed_change.get_id() if proposed_change else None,
            merge_started_at=branch.merge_started_at,
        )

    async def recover(self, *, force: bool = False, branch_name: str | None = None) -> RecoveryReport:
        """Recover the failed merge.

        Recovery always acts on a branch already flagged ``MERGE_FAILED``. It also acts on a branch
        stuck in ``MERGING`` when the merge is provably dead, and with ``force`` on one with an absent
        merge lock.

        When nothing needs recovering, clears a stale write-protection cache key if one names a branch
        that no longer exists (``ORPHANED_CLEARED``) or reports ``NOTHING_TO_RECOVER`` otherwise. On a
        recoverable branch, rolls the merge back, resets the proposed change and the branch to
        ``OPEN`` and lifts the write protection, returning ``RECOVERED`` or ``FAILED``.
        """
        recoverable = await self._find_recoverable(force=force, branch_name=branch_name)
        if recoverable is None:
            # A named branch that is not recoverable leaves any cache key belonging to another branch
            # in place; only auto-detect mode may clear an orphaned cache key.
            if branch_name is not None:
                return RecoveryReport(
                    outcome=RecoveryOutcome.NOTHING_TO_RECOVER, branch=None, proposed_change=None, merge_started_at=None
                )
            return await self._clear_orphaned_or_nothing()

        branch, proposed_change = recoverable
        merge_started_at = branch.merge_started_at
        proposed_change_id = proposed_change.get_id() if proposed_change else None

        log.info(
            "merge.recovery.started",
            branch=branch.name,
            merge_started_at=merge_started_at,
            proposed_change=proposed_change_id,
        )
        started_at = time.monotonic()
        try:
            await self._rollback(merge_started_at=merge_started_at)
            # Reset the proposed change before the branch: if a later step fails, the branch stays
            # flagged so a re-run re-detects it and finishes, rather than being reopened and losing the
            # link to the still-merging proposed change.
            await self._reset_proposed_change(proposed_change=proposed_change)
            await self._reset_branch(branch=branch)
            # Lift the write protection last, once the branch is back to OPEN, so a failure earlier in
            # the sequence leaves the protection in place for a re-run.
            await self.merge_write_blocker.delete()
        except Exception as exc:
            log.error("merge.recovery.failed", branch=branch.name, error=str(exc), exc_info=True)
            return RecoveryReport(
                outcome=RecoveryOutcome.FAILED,
                branch=branch.name,
                proposed_change=proposed_change_id,
                merge_started_at=merge_started_at,
            )

        log.info(
            "merge.recovery.completed",
            branch=branch.name,
            proposed_change=proposed_change_id,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
        return RecoveryReport(
            outcome=RecoveryOutcome.RECOVERED,
            branch=branch.name,
            proposed_change=proposed_change_id,
            merge_started_at=merge_started_at,
        )

    async def _find_recoverable(
        self, *, force: bool, branch_name: str | None
    ) -> tuple[Branch, CoreProposedChange | None] | None:
        """Return the recoverable branch and its associated proposed change, or ``None`` if none.

        Shared by the read-only preview and the mutating recovery so both agree on what is
        recoverable; the caller decides whether to act on the returned live objects.
        """
        branch = await self._find_recoverable_branch(force=force, branch_name=branch_name)
        if branch is None:
            return None
        proposed_change = await self._find_proposed_change(branch_name=branch.name)
        return branch, proposed_change

    async def _find_recoverable_branch(self, *, force: bool, branch_name: str | None) -> Branch | None:
        """Return the branch whose failed merge must be recovered, or ``None`` if none is found.

        A branch recorded ``MERGE_FAILED`` is always recoverable. A branch still ``MERGING`` is
        recoverable when its merge is provably dead — the merge lock is held by a worker that is no
        longer active and the grace period has passed. A ``MERGING`` branch whose lock holder is a live
        worker is a healthy merge and is left untouched.

        A ``MERGING`` branch with no lock is ambiguous and is gated behind ``force``. The missing lock
        could be caused by a cache flush during a healthy merge.
        """
        branches = await Branch.get_list(
            db=self.db,
            branch_filters=BranchListFilters(statuses=[BranchStatus.MERGE_FAILED, BranchStatus.MERGING]),
        )
        if branch_name is not None:
            branches = [b for b in branches if b.name == branch_name]

        failed = next((b for b in branches if b.status == BranchStatus.MERGE_FAILED), None)
        if failed is not None:
            return failed

        merging = [b for b in branches if b.status == BranchStatus.MERGING]
        if not merging:
            return None

        now = Timestamp()
        for branch in merging:
            if await self.identifier.should_mark_as_failed_merge(branch=branch, now=now):
                return branch
            if force and await self.identifier.merge_lock_holder() is None:
                return branch
        return None

    async def _clear_orphaned_or_nothing(self) -> RecoveryReport:
        """Clear the write-protection cache key only when the branch it names no longer exists.

        Reached when no branch needs recovering. A cache key naming a branch that still exists is left
        in place — that branch is either a healthy in-progress merge or one that was not auto-recovered.
        Only a cache key whose branch was removed out-of-band, or a malformed one with no identifiable
        branch, is orphaned and safe to drop. Transient cache errors are allowed to propagate so the
        key is never dropped on an unreadable-but-present value.
        """
        try:
            protection = await self.merge_write_blocker.get()
        except MalformedMergeProtectionError:
            # A present-but-unparseable cache key names no branch to recover but still blocks writes; drop it.
            log.warning("merge.recovery.orphaned_cleared")
            await self.merge_write_blocker.delete()
            return RecoveryReport(
                outcome=RecoveryOutcome.ORPHANED_CLEARED, branch=None, proposed_change=None, merge_started_at=None
            )

        if protection is None:
            return RecoveryReport(
                outcome=RecoveryOutcome.NOTHING_TO_RECOVER, branch=None, proposed_change=None, merge_started_at=None
            )

        existing = await Branch.get_list(db=self.db, name=protection.branch)
        if existing:
            return RecoveryReport(
                outcome=RecoveryOutcome.NOTHING_TO_RECOVER, branch=None, proposed_change=None, merge_started_at=None
            )

        log.warning("merge.recovery.orphaned_cleared", branch=protection.branch)
        await self.merge_write_blocker.delete()
        return RecoveryReport(
            outcome=RecoveryOutcome.ORPHANED_CLEARED,
            branch=protection.branch,
            proposed_change=None,
            merge_started_at=None,
        )

    async def _rollback(self, merge_started_at: str | None) -> None:
        """Reverse every default-branch write stamped at or after the merge start.

        Scoped to the default branch (the only merge target) and keyed on the merge start; the write
        block guarantees the merge owned every default-branch write in that window, so a range revert
        restores the pre-merge graph and per-node metadata. A missing timestamp means the cache key
        predates the recorded merge start and there is nothing to reverse.
        """
        if merge_started_at is None:
            return
        rollback_query = await RollbackQuery.init(
            db=self.db,
            branch=self.default_branch,
            target_branch=self.default_branch,
            at=Timestamp(merge_started_at),
            scope=RollbackScope.SINCE_TIMESTAMP,
            restore_metadata=True,
        )
        await rollback_query.execute(db=self.db)

    async def _reset_branch(self, branch: Branch) -> None:
        branch.status = BranchStatus.OPEN
        await branch.save(db=self.db)
        registry.branch[branch.name] = branch

    async def _find_proposed_change(self, branch_name: str) -> CoreProposedChange | None:
        proposed_changes = await NodeManager.query(
            db=self.db,
            schema=CoreProposedChange,
            filters={"source_branch__value": branch_name, "state__value": ProposedChangeState.MERGING.value},
            branch=self.default_branch,
        )
        return proposed_changes[0] if proposed_changes else None

    async def _reset_proposed_change(self, proposed_change: CoreProposedChange | None) -> None:
        if proposed_change is None:
            return
        # The state attribute is enum-backed: reads coerce back to the enum, writes take the raw value.
        proposed_change.state.value = ProposedChangeState.OPEN.value  # type: ignore[misc]
        await proposed_change.save(db=self.db)
