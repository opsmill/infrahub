from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.branch.status_checker import MERGE_RECOVERY_REQUIRED_MESSAGE, BranchStatusChecker
from infrahub.components import ComponentType
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.merge.failure_recoverer import RecoveryOutcome
from infrahub.core.merge.merge_locker import MERGE_LOCK_KEY
from infrahub.core.merge.write_blocker import MergeProtection, MergeProtectionState, MergeWriteBlocker
from infrahub.core.node import Node
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import MergeRecoveryRequiredError
from infrahub.services.component import InfrahubComponent
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder

from .conftest import (
    FailAtBranchResetRecoverer,
    FailAtLockReleaseRecoverer,
    build_identifier,
    build_recovery,
    find_logged_event,
)

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

DEAD_WORKER = "dead-worker"


def _lock_token(worker_id: str) -> str:
    return f"{Timestamp().to_string()}::{worker_id}"


class TestRecovery:
    """Recovery's non-happy paths: nothing to recover, orphaned marker, stuck merge, preview, delete gate."""

    @pytest.fixture
    async def cache(self) -> MemoryCache:
        return MemoryCache()

    @pytest.fixture
    async def component(self, db: InfrahubDatabase, cache: MemoryCache, default_branch: Branch) -> InfrahubComponent:
        # refresh_heartbeat marks THIS worker active, so a lock held by any other worker id is dead.
        component = InfrahubComponent(
            cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.API_SERVER
        )
        await component.refresh_heartbeat()
        return component

    async def test_no_failure_reports_nothing_to_recover(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)

        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.NOTHING_TO_RECOVER
        assert report.branch is None

    async def test_orphaned_marker_is_cleared_without_crashing(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        # The cache still names a protected branch, but that branch was removed out-of-band.
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch="branch-removed-out-of-band", state=MergeProtectionState.MERGE_FAILED)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.ORPHANED_CLEARED
        assert report.branch == "branch-removed-out-of-band"
        assert await blocker.get() is None

    async def test_stale_marker_for_reopened_branch_is_cleared(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        # A prior recovery reopened the branch to OPEN but its cache-key delete then failed, leaving a
        # stale MERGE_FAILED marker for a branch that is now OPEN. A re-run finishes the cleanup rather
        # than leaving default-branch writes blocked until the watcher reconciles.
        branch = Branch(
            name="recovery-reopened-stale-marker",
            status=BranchStatus.OPEN,
            branched_from=Timestamp().to_string(),
        )
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.ORPHANED_CLEARED
        assert report.branch == branch.name
        assert await blocker.get() is None

    async def test_stuck_merging_with_dead_lock_is_recovered(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        # A branch stuck in MERGING whose merge lock is held by a worker that is no longer alive. The
        # recurring scan deliberately leaves this ambiguous case alone; operator confirmation recovers.
        branch = Branch(
            name="recovery-stuck-merging",
            status=BranchStatus.MERGING,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        await cache.set(MERGE_LOCK_KEY, _lock_token(DEAD_WORKER))
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGING)

        recovery = build_recovery(
            db=db, cache=cache, component=component, default_branch=default_branch, grace_period_seconds=0
        )
        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.RECOVERED
        assert report.branch == branch.name
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert await blocker.get() is None
        # The stale merge lock the dead worker held is released, so the next merge is not blocked until
        # the deadlock-cleanup cron runs.
        assert await cache.get(MERGE_LOCK_KEY) is None

    async def test_preview_is_read_only_then_recover_recovers(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        branch = Branch(
            name="recovery-preview",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)

        # Preview reports the branch as recoverable and makes no changes.
        preview = await recovery.preview()
        assert preview.outcome == RecoveryOutcome.RECOVERABLE
        assert preview.branch == branch.name
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
        assert await blocker.get() == MergeProtection(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        # A subsequent recover actually recovers the branch.
        report = await recovery.recover()
        assert report.outcome == RecoveryOutcome.RECOVERED
        assert report.branch == branch.name
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert await blocker.get() is None

    async def test_failed_branch_delete_is_rejected_then_allowed_after_recovery(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        branch = Branch(
            name="recovery-delete-gate",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        # The same gate the mutation middleware runs for BranchDelete refuses the failed branch.
        checker = BranchStatusChecker(db=db, merge_write_blocker=blocker)
        with pytest.raises(MergeRecoveryRequiredError, match=re.escape(MERGE_RECOVERY_REQUIRED_MESSAGE)):
            await checker.check_merging_status(branch=branch)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover()
        assert report.outcome == RecoveryOutcome.RECOVERED

        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        # With the branch reopened and the protection lifted, the delete gate no longer blocks it.
        await checker.check_merging_status(branch=reloaded)

    async def test_healthy_in_progress_merge_marker_is_retained(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        # A healthy in-progress merge: the branch is MERGING and the merge lock is held by THIS live
        # worker (refresh_heartbeat marked it active). The read-only preview must leave it alone.
        branch = Branch(
            name="recovery-healthy-merging",
            status=BranchStatus.MERGING,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        await cache.set(MERGE_LOCK_KEY, _lock_token(WORKER_IDENTITY))
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGING)

        recovery = build_recovery(
            db=db, cache=cache, component=component, default_branch=default_branch, grace_period_seconds=0
        )
        report = await recovery.preview()

        assert report.outcome == RecoveryOutcome.NOTHING_TO_RECOVER
        # The healthy merge still owns the protection; the preview must not have lifted it.
        assert await blocker.get() == MergeProtection(branch=branch.name, state=MergeProtectionState.MERGING)
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGING

    async def test_recovery_failure_holds_protection(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        branch = Branch(
            name="recovery-failed-step",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = FailAtBranchResetRecoverer(
            db=db,
            merge_write_blocker=blocker,
            identifier=build_identifier(db=db, cache=cache, component=component, default_branch=default_branch),
            default_branch=default_branch,
            cache=cache,
            rollbacker=GraphRollbacker(db=db),
        )

        with caplog.at_level("ERROR", logger="infrahub"):
            report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.FAILED
        assert report.branch == branch.name
        # The failing step leaves the branch flagged and the protection held for a re-run.
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
        assert await blocker.get() == MergeProtection(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)
        # The failure is observable: a locatable entry records which branch's recovery failed.
        assert find_logged_event(caplog, event="merge.recovery.failed", branch=branch.name) is not None

    async def test_lock_release_failure_holds_protection_and_lock(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        branch = Branch(
            name="recovery-lock-release-failed",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        lock_token = _lock_token(DEAD_WORKER)
        await cache.set(MERGE_LOCK_KEY, lock_token)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = FailAtLockReleaseRecoverer(
            db=db,
            merge_write_blocker=blocker,
            identifier=build_identifier(db=db, cache=cache, component=component, default_branch=default_branch),
            default_branch=default_branch,
            cache=cache,
            rollbacker=GraphRollbacker(db=db),
        )

        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.FAILED
        assert report.branch == branch.name
        # A swallowed lock-release failure would report success while leaving merges permanently blocked;
        # instead the branch stays flagged, the protection held and the lock in place for a re-run.
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
        assert await blocker.get() == MergeProtection(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)
        assert await cache.get(MERGE_LOCK_KEY) == lock_token

    async def test_absent_lock_merging_is_gated_by_force(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        # A branch stuck in MERGING with the merge lock absent (ambiguous: no lock token is set).
        branch = Branch(
            name="recovery-absent-lock",
            status=BranchStatus.MERGING,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGING)

        recovery = build_recovery(
            db=db, cache=cache, component=component, default_branch=default_branch, grace_period_seconds=0
        )

        # Without force the ambiguous absent-lock case is left alone and the marker is retained.
        without_force = await recovery.recover(force=False)
        assert without_force.outcome == RecoveryOutcome.NOTHING_TO_RECOVER
        assert await blocker.get() == MergeProtection(branch=branch.name, state=MergeProtectionState.MERGING)
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGING

        # Force lets the operator override and recover it.
        with_force = await recovery.recover(force=True)
        assert with_force.outcome == RecoveryOutcome.RECOVERED
        assert with_force.branch == branch.name
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert await blocker.get() is None

    async def test_proposed_change_is_reset_to_open(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        branch = Branch(
            name="recovery-proposed-change",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
        )
        await branch.save(db=db)

        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name="pc-recovery", source_branch=branch.name, destination_branch="main", state="merging"
        )
        await proposed_change.save(db=db)

        # Captured after the proposed change is created so the rollback window holds none of the setup.
        branch.merge_started_at = Timestamp().to_string()
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover()

        assert report.outcome == RecoveryOutcome.RECOVERED
        assert report.proposed_change == proposed_change.id
        reloaded_pc = await NodeManager.get_one(db=db, id=proposed_change.id, raise_on_error=True)
        assert reloaded_pc.state.value.value == "open"  # type: ignore[attr-defined]

    async def test_named_branch_is_targeted(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        branch = Branch(
            name="recovery-named-target",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        with caplog.at_level("INFO", logger="infrahub"):
            report = await recovery.recover(branch_name=branch.name)

        assert report.outcome == RecoveryOutcome.RECOVERED
        assert report.branch == branch.name
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.OPEN
        assert await blocker.get() is None
        # A completed recovery brackets its work with locatable start and completion entries.
        assert find_logged_event(caplog, event="merge.recovery.started", branch=branch.name) is not None
        assert find_logged_event(caplog, event="merge.recovery.completed", branch=branch.name) is not None

    async def test_named_branch_that_is_not_recoverable_leaves_other_markers(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        cache: MemoryCache,
        component: InfrahubComponent,
    ) -> None:
        # A genuinely failed branch owns the protection marker, but the operator names a different,
        # healthy branch. Recovery must not touch the failed branch's marker.
        failed_branch = Branch(
            name="recovery-named-failed",
            status=BranchStatus.MERGE_FAILED,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await failed_branch.save(db=db)
        healthy_branch = Branch(
            name="recovery-named-healthy",
            status=BranchStatus.OPEN,
            branched_from=Timestamp().to_string(),
        )
        await healthy_branch.save(db=db)
        blocker = MergeWriteBlocker(cache=cache)
        await blocker.set(branch=failed_branch.name, state=MergeProtectionState.MERGE_FAILED)

        recovery = build_recovery(db=db, cache=cache, component=component, default_branch=default_branch)
        report = await recovery.recover(branch_name=healthy_branch.name)

        assert report.outcome == RecoveryOutcome.NOTHING_TO_RECOVER
        assert report.branch is None
        # The failed branch and its marker are untouched.
        reloaded = await Branch.get_by_name(db=db, name=failed_branch.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
        assert await blocker.get() == MergeProtection(
            branch=failed_branch.name, state=MergeProtectionState.MERGE_FAILED
        )
