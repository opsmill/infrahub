from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.lock import InfrahubLock, InfrahubLockRegistry

if TYPE_CHECKING:
    import redis.asyncio as redis

    from infrahub.services import InfrahubServices


class LockAction(StrEnum):
    ACQUIRE = "acquire"
    RELEASE = "release"
    CHECKPOINT = "checkpoint"


@dataclass
class LockEvent:
    """A single entry in a lock timeline: a lock transition or an arbitrary checkpoint."""

    seq: int
    name: str
    action: LockAction
    label: str | None = None


class LockTimeline:
    """Ordered, monotonic log of lock transitions shared by every recorder in a test."""

    def __init__(self) -> None:
        self.events: list[LockEvent] = []
        self._seq = itertools.count()

    def record(self, name: str, action: LockAction, label: str | None = None) -> int:
        seq = next(self._seq)
        self.events.append(LockEvent(seq=seq, name=name, action=action, label=label))
        return seq

    def checkpoint(self, label: str) -> int:
        """Mark a point of interest in the timeline so tests can ask which locks were held at it."""
        return self.record(name=label, action=LockAction.CHECKPOINT, label=label)

    def held_at(self, seq: int) -> set[str]:
        """Return the set of lock names held at the moment ``seq`` was recorded."""
        held: set[str] = set()
        for event in self.events:
            if event.seq >= seq:
                break
            if event.action == LockAction.ACQUIRE:
                held.add(event.name)
            elif event.action == LockAction.RELEASE:
                held.discard(event.name)
        return held

    def currently_held(self) -> set[str]:
        held: set[str] = set()
        for event in self.events:
            if event.action == LockAction.ACQUIRE:
                held.add(event.name)
            elif event.action == LockAction.RELEASE:
                held.discard(event.name)
        return held

    def acquire_sequence(self, prefix: str | None = None) -> list[str]:
        """Return the lock names in the order they were acquired, optionally filtered by name prefix."""
        return [
            event.name
            for event in self.events
            if event.action == LockAction.ACQUIRE and (prefix is None or event.name.startswith(prefix))
        ]

    def checkpoint_seqs(self, label: str) -> list[int]:
        return [event.seq for event in self.events if event.action == LockAction.CHECKPOINT and event.label == label]

    # --- assertion helpers ---

    def assert_held_at_checkpoint(self, lock_name: str, label: str, *, expected: bool) -> None:
        seqs = self.checkpoint_seqs(label)
        if not seqs:
            raise AssertionError(f"No checkpoint named {label!r} was recorded")
        for seq in seqs:
            actually_held = lock_name in self.held_at(seq)
            if actually_held is not expected:
                raise AssertionError(
                    f"At checkpoint {label!r}, expected lock {lock_name!r} held={expected} but held={actually_held}. "
                    f"Held at that point: {sorted(self.held_at(seq))}"
                )

    def assert_never_overlap(self, lock_a: str, lock_b: str) -> None:
        held: set[str] = set()
        for event in self.events:
            if event.action == LockAction.ACQUIRE:
                held.add(event.name)
                if lock_a in held and lock_b in held:
                    raise AssertionError(f"Locks {lock_a!r} and {lock_b!r} were held simultaneously")
            elif event.action == LockAction.RELEASE:
                held.discard(event.name)


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

    def __init__(self, timeline: LockTimeline | None = None) -> None:
        super().__init__(local_only=True)
        self.timeline = timeline or LockTimeline()

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
    registry = RecordingLockRegistry(timeline=timeline)
    lock.registry = registry
    return registry.timeline
