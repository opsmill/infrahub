from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection


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

    def assert_held_at_checkpoint(self, lock_name: str, label: str) -> None:
        """Assert that ``lock_name`` was held at every checkpoint named ``label``."""
        self._assert_held_at_checkpoint(lock_name, label, expected=True)

    def assert_not_held_at_checkpoint(self, lock_name: str, label: str) -> None:
        """Assert that ``lock_name`` was not held at any checkpoint named ``label``."""
        self._assert_held_at_checkpoint(lock_name, label, expected=False)

    def _assert_held_at_checkpoint(self, lock_name: str, label: str, *, expected: bool) -> None:
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

    def assert_never_overlap(self, lock_names: Collection[str]) -> None:
        """Assert that no two of ``lock_names`` were ever held at the same time.

        Raises:
            AssertionError: if two or more of ``lock_names`` were held simultaneously.

        """
        watched = set(lock_names)
        held: set[str] = set()
        for event in self.events:
            if event.action == LockAction.ACQUIRE:
                held.add(event.name)
                overlap = held & watched
                if len(overlap) > 1:
                    raise AssertionError(f"Locks {sorted(overlap)} were held simultaneously")
            elif event.action == LockAction.RELEASE:
                held.discard(event.name)
