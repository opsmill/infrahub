from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.lock import InfrahubLock, InfrahubLockRegistry

from .timeline import LockAction, LockTimeline

if TYPE_CHECKING:
    import redis.asyncio as redis

    from infrahub.services import InfrahubServices


class RecordingLock(InfrahubLock):
    """A local lock that logs its real (non-re-entrant) acquire/release boundaries to a timeline."""

    def __init__(
        self,
        name: str,
        connection: redis.Redis | InfrahubServices | None = None,
        in_multi: bool = False,
        metrics: bool = True,
        *,
        timeline: LockTimeline,
    ) -> None:
        super().__init__(name=name, connection=connection, in_multi=in_multi, metrics=metrics)
        self._timeline = timeline

    async def acquire(self) -> None:
        reentrant = self._recursion_var.get() is not None
        await super().acquire()
        if not reentrant:
            self._timeline.record(self.name, LockAction.ACQUIRE)

    async def release(self) -> None:
        will_release = self._recursion_var.get() == 1
        await super().release()
        if will_release:
            self._timeline.record(self.name, LockAction.RELEASE)


class RecordingLockRegistry(InfrahubLockRegistry):
    """Local-only lock registry that hands out ``RecordingLock`` instances backed by a shared timeline."""

    def __init__(self, timeline: LockTimeline) -> None:
        super().__init__(local_only=True)
        self.timeline = timeline

    def get(
        self,
        name: str,
        namespace: str | None = None,
        local: bool | None = None,
        in_multi: bool = False,
        metrics: bool = True,
    ) -> InfrahubLock:
        lock_name = self.name_generator.generate_name(name=name, namespace=namespace, local=local)
        if lock_name not in self.locks:
            self.locks[lock_name] = RecordingLock(
                name=lock_name,
                connection=self.connection,
                in_multi=in_multi,
                metrics=metrics,
                timeline=self.timeline,
            )
        return self.locks[lock_name]


def install_recording_lock_registry(timeline: LockTimeline | None = None) -> LockTimeline:
    """Replace the global lock registry with a recording one and return its timeline."""
    timeline = timeline or LockTimeline()
    lock.registry = RecordingLockRegistry(timeline=timeline)
    return timeline
