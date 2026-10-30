from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub import config, lock
from infrahub.lock import InfrahubLock, InfrahubLockRegistry, InfrahubSharedLock

from .timeline import LockAction, LockTimeline

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

    import redis.asyncio as redis

    from infrahub.locks.shared_holders import SharedHolderStore
    from infrahub.services import InfrahubServices

GATE_TIMEOUT_SECONDS = 30


class RecordingLock(InfrahubLock):
    """A local lock that logs its real (non-re-entrant) waits, acquires and releases to a timeline."""

    def __init__(
        self,
        name: str,
        connection: redis.Redis | InfrahubServices | None = None,
        in_multi: bool = False,
        metrics: bool = True,
        ttl: int | None = None,
        *,
        timeline: LockTimeline,
    ) -> None:
        super().__init__(name=name, connection=connection, in_multi=in_multi, metrics=metrics, ttl=ttl)
        self._timeline = timeline

    async def acquire(self) -> None:
        if self._recursion_var.get() is not None:
            await super().acquire()
            return
        self._timeline.record(self.name, LockAction.WAIT)
        try:
            await super().acquire()
        except BaseException:
            # A cancelled or failed wait leaves the queue, so the count of waiters must drop too.
            self._timeline.record(self.name, LockAction.ABANDON)
            raise
        self._timeline.record(self.name, LockAction.ACQUIRE)

    async def release(self) -> None:
        will_release = self._recursion_var.get() == 1
        await super().release()
        if will_release:
            self._timeline.record(self.name, LockAction.RELEASE)


class LockGate:
    """Holds the first task that takes a lock in a given mode until the test releases it."""

    def __init__(self) -> None:
        self._reached = asyncio.Event()
        self._released = asyncio.Event()

    async def wait_reached(self) -> None:
        await asyncio.wait_for(self._reached.wait(), timeout=GATE_TIMEOUT_SECONDS)

    def release(self) -> None:
        self._released.set()

    async def hold(self) -> None:
        self._reached.set()
        await asyncio.wait_for(self._released.wait(), timeout=GATE_TIMEOUT_SECONDS)


class RecordingSharedLock(InfrahubSharedLock):
    """A local shared lock that logs each mode it is taken in as ``<name>:shared`` or ``<name>:exclusive``.

    A gate registered for one of those names holds the first task that takes the lock in that mode.
    """

    def __init__(
        self,
        name: str,
        mutex: InfrahubLock,
        store: SharedHolderStore,
        ttl_seconds: int,
        wait_seconds: float,
        *,
        timeline: LockTimeline,
        gates: dict[str, LockGate],
    ) -> None:
        super().__init__(
            name=name, mutex=mutex, store=store, ttl_seconds=ttl_seconds, wait_seconds=wait_seconds, poll_seconds=0.01
        )
        self._timeline = timeline
        self._gates = gates

    async def acquire_shared(self) -> None:
        if self._hold.get() is not None:
            await super().acquire_shared()
            return
        await self._record_acquire(name=f"{self.name}:shared", acquire=super().acquire_shared())

    async def release_shared(self) -> None:
        hold = self._hold.get()
        await super().release_shared()
        if hold is not None and hold.depth == 1:
            self._timeline.record(f"{self.name}:shared", LockAction.RELEASE)

    async def acquire_exclusive(self) -> None:
        await self._record_acquire(name=f"{self.name}:exclusive", acquire=super().acquire_exclusive())

    async def release_exclusive(self) -> None:
        await super().release_exclusive()
        self._timeline.record(f"{self.name}:exclusive", LockAction.RELEASE)

    async def _record_acquire(self, name: str, acquire: Coroutine[Any, Any, None]) -> None:
        self._timeline.record(name, LockAction.WAIT)
        try:
            await acquire
        except BaseException:
            self._timeline.record(name, LockAction.ABANDON)
            raise
        self._timeline.record(name, LockAction.ACQUIRE)
        gate = self._gates.pop(name, None)
        if gate is not None:
            await gate.hold()


class RecordingLockRegistry(InfrahubLockRegistry):
    """Local-only lock registry that hands out recording locks backed by a shared timeline."""

    def __init__(self, timeline: LockTimeline) -> None:
        super().__init__(local_only=True)
        self.timeline = timeline
        self.gates: dict[str, LockGate] = {}

    def gate(self, name: str) -> LockGate:
        """Return a gate holding the first task that next takes the lock ``name`` in the mode its suffix names."""
        gate = LockGate()
        self.gates[name] = gate
        return gate

    def _create_shared_lock(self, name: str) -> InfrahubSharedLock:
        return RecordingSharedLock(
            name=name,
            mutex=self.get(name=name),
            store=self.shared_holder_store,
            ttl_seconds=config.SETTINGS.cache.shared_lock_ttl_secs,
            wait_seconds=config.SETTINGS.cache.exclusive_lock_wait_secs,
            timeline=self.timeline,
            gates=self.gates,
        )

    def _create_lock(self, name: str, in_multi: bool, metrics: bool, ttl: int | None) -> InfrahubLock:
        return RecordingLock(
            name=name,
            connection=self.connection,
            in_multi=in_multi,
            metrics=metrics,
            ttl=ttl,
            timeline=self.timeline,
        )


def install_recording_lock_registry(timeline: LockTimeline | None = None) -> LockTimeline:
    """Replace the global lock registry with a recording one and return its timeline."""
    timeline = timeline or LockTimeline()
    lock.registry = RecordingLockRegistry(timeline=timeline)
    return timeline
