"""Bound the memory one process uses to hold stored objects while it encrypts them.

An object is held in memory from the moment it is read until its encrypted copy is written, and then about three
times over: the content, the envelope and one transient copy. A claim takes `MEMORY_FACTOR` times the size of the
object from a fixed number of bytes, so the sum over the objects in memory never exceeds that number, whatever the
number of requests, the number of objects per request or their sizes.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType

MEMORY_FACTOR = 3
"""Bytes of memory held while an object is encrypted, per byte of the object."""


class MemoryBudgetBusyError(Exception):
    """The memory an object needs was not free within the time the caller accepts to wait."""

    def __init__(self, needed: int, capacity: int) -> None:
        self.needed = needed
        self.capacity = capacity
        super().__init__(f"{needed} bytes of the {capacity} bytes of encryption memory are not free")


class MemoryBudget:
    """A fixed number of bytes that threads claim before they hold an object in memory and release afterwards."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._used = 0
        self._changed = threading.Condition()

    @property
    def largest_object(self) -> int:
        """Size in bytes of the largest object this budget can ever hold."""
        return self.capacity // MEMORY_FACTOR

    def claim(self, size: int, wait_seconds: float) -> int:
        """Take the memory for an object of `size` bytes and return the number of bytes taken.

        Waits at most `wait_seconds` for other objects to leave memory.

        Raises:
            MemoryBudgetBusyError: If the memory is still not free after `wait_seconds`.
            ValueError: If the object is larger than `largest_object`, so it could never be held.

        """
        needed = size * MEMORY_FACTOR
        if needed > self.capacity:
            raise ValueError(f"An object of {size} bytes needs {needed} bytes, more than the budget of {self.capacity}")
        with self._changed:
            if not self._changed.wait_for(lambda: self._used + needed <= self.capacity, timeout=wait_seconds):
                raise MemoryBudgetBusyError(needed=needed, capacity=self.capacity)
            self._used += needed
        return needed

    def release(self, needed: int) -> None:
        """Give back bytes that `claim` returned."""
        with self._changed:
            self._used -= needed
            self._changed.notify_all()

    def holding(self, wait_seconds: float) -> MemoryHold:
        """Return a context manager that holds what the object it is told about needs, until the block ends."""
        return MemoryHold(budget=self, wait_seconds=wait_seconds)


class MemoryHold:
    """The memory one object holds, released when the block ends, including when it ends with an exception."""

    def __init__(self, budget: MemoryBudget, wait_seconds: float) -> None:
        self._budget = budget
        self._wait_seconds = wait_seconds
        self._held = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        if self._held:
            self._budget.release(self._held)
            self._held = 0

    def take(self, size: int) -> None:
        """Claim the memory for an object of `size` bytes; a hold takes memory once.

        Raises:
            MemoryBudgetBusyError: If the memory is not free within the time this hold waits.
            RuntimeError: If this hold already took its memory.

        """
        if self._held:
            raise RuntimeError("This hold already took its memory")
        self._held = self._budget.claim(size=size, wait_seconds=self._wait_seconds)


class ProcessMemoryBudget:
    """The one budget of the process, rebuilt when the configured number of bytes changes."""

    def __init__(self) -> None:
        self._budget: MemoryBudget | None = None
        self._lock = threading.Lock()

    def current(self, capacity: int) -> MemoryBudget:
        """Return the budget of this process, a new one when `capacity` differs from the last call."""
        with self._lock:
            if self._budget is None or self._budget.capacity != capacity:
                self._budget = MemoryBudget(capacity=capacity)
            return self._budget
