from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING, Callable, Protocol

from infrahub.log import get_logger

from .priority import Priority

if TYPE_CHECKING:
    from asyncio import Future

log = get_logger()


class SlotPoolObserver(Protocol):
    """Sink notified after a class's in-flight or waiter count changes.

    Receives the new counts as arguments, so it never reads back from the pool: the
    dependency runs one way, from pool to sink.
    """

    def on_counts_changed(self, priority: Priority, *, in_flight: int, waiters: int) -> None: ...


class Acquisition:
    """Handle for a held slot, carrying the priority class and measured sojourn.

    A plain data holder handed out by the pool and handed back to release the slot. The
    ``_released`` guard the pool checks makes returning the same handle twice a no-op, so
    releasing in a ``finally`` is safe even on a path that already released.
    """

    def __init__(self, *, priority: Priority, sojourn: float) -> None:
        self.priority = priority
        """Priority class the slot was acquired for."""

        self.sojourn = sojourn
        """Seconds spent waiting to acquire the slot (``0.0`` on the fast path)."""

        self._released = False


class PrioritySlotPool:
    """Bounded concurrency primitive with per-class FIFO waiter queues.

    Holds ``max_concurrency`` slots shared across the priority classes. A freed slot is
    handed to the highest-priority non-empty waiter queue, FIFO within that class. The
    acquire path is cancellation-safe, modelled on the standard library semaphore: a
    cancelled waiter deregisters itself and, if a slot was handed to it in the same tick,
    re-releases that slot to the next eligible waiter so no slot is ever leaked.
    """

    def __init__(
        self,
        *,
        max_concurrency: int,
        observers: list[SlotPoolObserver],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_concurrency = max_concurrency
        self._available = max_concurrency
        self._clock = clock
        self._waiters: dict[Priority, deque[Future[bool]]] = {priority: deque() for priority in Priority}
        self._in_flight: dict[Priority, int] = dict.fromkeys(Priority, 0)
        self._observers = observers

    def _notify(self, priority: Priority) -> None:
        """Push a class's current counts to every observer.

        Each observer is isolated on its own: the sinks are best-effort and run mid-transition,
        so a failing one must neither corrupt admission state (leak a slot, strand a waiter),
        surface to the caller, nor skip the observers behind it.
        """
        if not self._observers:
            return
        in_flight = self._in_flight[priority]
        waiters = len(self._waiters[priority])
        for observer in self._observers:
            try:
                observer.on_counts_changed(priority, in_flight=in_flight, waiters=waiters)
            except Exception:
                log.warning("admission slot-pool observer raised; continuing", exc_info=True)

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
                self._return_slot()
            raise

        sojourn = self._clock() - enqueue_time
        return self._make_acquisition(priority=priority, sojourn=sojourn)

    def release(self, *, acquisition: Acquisition) -> None:
        """Return a served request's slot and hand it to the highest-priority waiter, if any.

        Idempotent per acquisition: returning the same handle again is a no-op, so releasing
        in a ``finally`` is always safe even when an earlier path already released.
        """
        if acquisition._released:
            return
        acquisition._released = True
        self._in_flight[acquisition.priority] -= 1
        self._notify(acquisition.priority)
        self._return_slot()

    def _return_slot(self) -> None:
        """Return a raw slot to the pool and hand it to the highest-priority waiter, if any."""
        self._available += 1
        self._wake_up_next()

    def _wake_up_next(self) -> None:
        """Hand the just-freed slot to the highest-priority waiting request.

        Scans the per-class waiter queues in priority order and resolves the first
        not-yet-done waiter's future with ``set_result(True)``, decrementing ``_available``
        for the handed-out slot. Done or cancelled futures are skipped.
        """
        for priority in Priority:
            for future in self._waiters[priority]:
                if not future.done():
                    self._available -= 1
                    future.set_result(True)
                    return

    def _make_acquisition(self, *, priority: Priority, sojourn: float) -> Acquisition:
        self._in_flight[priority] += 1
        self._notify(priority)
        return Acquisition(priority=priority, sojourn=sojourn)
