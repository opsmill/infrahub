from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING, Callable

from .priority import Priority

if TYPE_CHECKING:
    from asyncio import Future


class Acquisition:
    """Handle for a held slot, carrying the priority class and measured sojourn.

    ``release`` returns the slot to the pool and is safe to call more than once; use it
    in a ``finally`` so the slot is always returned even when the handler raises.
    """

    def __init__(self, *, priority: Priority, sojourn: float, pool: PrioritySlotPool) -> None:
        self.priority = priority
        """Priority class the slot was acquired for."""

        self.sojourn = sojourn
        """Seconds spent waiting to acquire the slot (``0.0`` on the fast path)."""

        self._pool = pool
        self._released = False

    def release(self) -> None:
        """Return the slot to the pool. Idempotent."""
        if self._released:
            return
        self._released = True
        self._pool._release_acquisition(priority=self.priority)


class PrioritySlotPool:
    """Bounded concurrency primitive with per-class FIFO waiter queues.

    Holds ``max_concurrency`` slots shared across the priority classes. A freed slot is
    handed to the highest-priority non-empty waiter queue, FIFO within that class. The
    acquire path is cancellation-safe, modelled on the standard library semaphore: a
    cancelled waiter deregisters itself and, if a slot was handed to it in the same tick,
    re-releases that slot to the next eligible waiter so no slot is ever leaked.
    """

    def __init__(self, *, max_concurrency: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._max_concurrency = max_concurrency
        self._available = max_concurrency
        self._clock = clock
        self._waiters: dict[Priority, deque[Future[bool]]] = {priority: deque() for priority in Priority}
        self._in_flight: dict[Priority, int] = dict.fromkeys(Priority, 0)
        self._on_change: Callable[[Priority], None] | None = None

    def set_observer(self, on_change: Callable[[Priority], None] | None) -> None:
        """Register a callback invoked with a class whenever its waiter or in-flight count changes.

        This lets an external observer (e.g. metric gauges) track queue depth the moment
        a request enqueues or leaves the queue, rather than only when some other request is
        admitted or released. The primitive itself stays free of any metrics dependency.
        """
        self._on_change = on_change

    def _notify(self, priority: Priority) -> None:
        if self._on_change is not None:
            self._on_change(priority)

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def available(self) -> int:
        return self._available

    def in_flight(self, priority: Priority) -> int:
        """Number of admitted-and-running requests for a class."""
        return self._in_flight[priority]

    def waiters(self, priority: Priority) -> int:
        """Number of requests currently queued waiting for a slot in a class."""
        return len(self._waiters[priority])

    async def acquire(self, *, priority: Priority) -> Acquisition:
        """Acquire a slot, waiting behind higher-priority classes when the pool is full.

        Args:
            priority: The class to enqueue under while waiting.

        Returns:
            An ``Acquisition`` whose ``sojourn`` is the time spent waiting.

        Raises:
            CancelledError: If the waiting task is cancelled; the slot is never leaked.

        """
        if self._available > 0:
            self._available -= 1
            return self._make_acquisition(priority=priority, sojourn=0.0)

        loop = asyncio.get_running_loop()
        future: Future[bool] = loop.create_future()
        queue = self._waiters[priority]
        queue.append(future)
        self._notify(priority)
        enqueue_time = self._clock()

        try:
            try:
                await future
            finally:
                if future in queue:
                    queue.remove(future)
                    self._notify(priority)
        except asyncio.CancelledError:
            if not future.cancelled():
                # A slot was handed to us in the same tick but we were cancelled before
                # consuming it: re-release it so the next eligible waiter is served.
                self.release()
            raise

        sojourn = self._clock() - enqueue_time
        return self._make_acquisition(priority=priority, sojourn=sojourn)

    def release(self) -> None:
        """Return a slot and hand it to the highest-priority waiter, if any."""
        self._available += 1
        self._wake_up_next()

    def _wake_up_next(self) -> None:
        for priority in Priority:
            for future in self._waiters[priority]:
                if not future.done():
                    self._available -= 1
                    future.set_result(True)
                    return

    def _make_acquisition(self, *, priority: Priority, sojourn: float) -> Acquisition:
        self._in_flight[priority] += 1
        self._notify(priority)
        return Acquisition(priority=priority, sojourn=sojourn, pool=self)

    def _release_acquisition(self, *, priority: Priority) -> None:
        self._in_flight[priority] -= 1
        self._notify(priority)
        self.release()
