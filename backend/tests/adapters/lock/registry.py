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

    def __init__(  # noqa: PLR0913
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
