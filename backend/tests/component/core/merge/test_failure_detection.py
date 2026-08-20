from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.components import ComponentType
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.failure_identifier import MergeFailureIdentifier
from infrahub.core.merge.merge_locker import MERGE_LOCK_KEY
from infrahub.core.merge.write_blocker import MergeProtection, MergeProtectionState, MergeWriteBlocker
from infrahub.core.timestamp import Timestamp
from infrahub.services.component import InfrahubComponent
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder

from .conftest import find_logged_event

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

DEAD_WORKER = "dead-worker"
# Shorter than the 600s head start given to merging_branch_for_10m, longer than the zero-age branch in the
# within-grace test.
GRACE_PERIOD_SECONDS = 180


def _lock_token(worker_id: str) -> str:
    return f"{Timestamp().to_string()}::{worker_id}"


class TestFailureDetection:
    """Detection flips a dead merge to MERGE_FAILED and holds the protection key (real db)."""

    @pytest.fixture
    async def cache(self) -> MemoryCache:
        return MemoryCache()

    @pytest.fixture
    async def component(self, db: InfrahubDatabase, cache: MemoryCache, default_branch: Branch) -> InfrahubComponent:
        # refresh_heartbeat marks THIS worker active
        component = InfrahubComponent(
            cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.API_SERVER
        )
        await component.refresh_heartbeat()
        return component

    def _identifier(
        self, db: InfrahubDatabase, cache: MemoryCache, component: InfrahubComponent, default_branch: Branch
    ) -> MergeFailureIdentifier:
        return MergeFailureIdentifier(
            db=db,
            cache=cache,
            component=component,
            merge_write_blocker=MergeWriteBlocker(cache=cache),
            default_branch=default_branch,
            grace_period_seconds=GRACE_PERIOD_SECONDS,
        )

    @pytest.fixture
    async def merging_branch_for_10m(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        branch = Branch(
            name="failure-detection-merging",
            status=BranchStatus.MERGING,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().add(seconds=-600).to_string(),
        )
        await branch.save(db=db)
        return branch

    async def test_dead_holder_past_grace_is_flagged(
        self,
        db: InfrahubDatabase,
        cache: MemoryCache,
        component: InfrahubComponent,
        merging_branch_for_10m: Branch,
        default_branch: Branch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await cache.set(MERGE_LOCK_KEY, _lock_token(DEAD_WORKER))
        recovery = self._identifier(db, cache, component, default_branch)

        with caplog.at_level("WARNING", logger="infrahub"):
            flagged = await recovery.scan()

        assert flagged == merging_branch_for_10m.name
        reloaded = await Branch.get_by_name(db=db, name=merging_branch_for_10m.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
        assert await MergeWriteBlocker(cache=cache).get() == MergeProtection(
            branch=merging_branch_for_10m.name, state=MergeProtectionState.MERGE_FAILED
        )
        # Detection emits a structured entry an operator can locate by branch, carrying the dead worker.
        logged = find_logged_event(caplog, event="merge.failure.detected", branch=merging_branch_for_10m.name)
        assert logged is not None
        assert logged["worker_id"] == DEAD_WORKER
        assert logged["merge_started_at"] == merging_branch_for_10m.merge_started_at

    async def test_active_holder_is_not_flagged(
        self,
        db: InfrahubDatabase,
        cache: MemoryCache,
        component: InfrahubComponent,
        merging_branch_for_10m: Branch,
        default_branch: Branch,
    ) -> None:
        await cache.set(MERGE_LOCK_KEY, _lock_token(WORKER_IDENTITY))
        recovery = self._identifier(db, cache, component, default_branch)

        assert await recovery.scan() is None
        reloaded = await Branch.get_by_name(db=db, name=merging_branch_for_10m.name)
        assert reloaded.status == BranchStatus.MERGING

    async def test_within_grace_is_not_flagged(
        self, db: InfrahubDatabase, cache: MemoryCache, component: InfrahubComponent, default_branch: Branch
    ) -> None:
        branch = Branch(
            name="failure-detection-young-merge",
            status=BranchStatus.MERGING,
            branched_from=Timestamp().to_string(),
            merge_started_at=Timestamp().to_string(),
        )
        await branch.save(db=db)
        await cache.set(MERGE_LOCK_KEY, _lock_token(DEAD_WORKER))
        recovery = self._identifier(db, cache, component, default_branch)

        assert await recovery.scan() is None
        reloaded = await Branch.get_by_name(db=db, name=branch.name)
        assert reloaded.status == BranchStatus.MERGING

    async def test_scan_is_idempotent(
        self,
        db: InfrahubDatabase,
        cache: MemoryCache,
        component: InfrahubComponent,
        merging_branch_for_10m: Branch,
        default_branch: Branch,
    ) -> None:
        await cache.set(MERGE_LOCK_KEY, _lock_token(DEAD_WORKER))
        recovery = self._identifier(db, cache, component, default_branch)

        assert await recovery.scan() == merging_branch_for_10m.name
        # A second pass finds no MERGING branch (it is now MERGE_FAILED), so it is a no-op.
        assert await recovery.scan() is None
        reloaded = await Branch.get_by_name(db=db, name=merging_branch_for_10m.name)
        assert reloaded.status == BranchStatus.MERGE_FAILED
