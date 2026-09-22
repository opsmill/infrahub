from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Awaitable, Callable

from infrahub import config
from infrahub.log import get_logger
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.component import refresh_worker_heartbeat

if TYPE_CHECKING:
    from infrahub.components import ComponentType
    from infrahub.services.protocols import InfrahubLogger

HEARTBEAT_INTERVAL_SECONDS = 5.0
"""Seconds between the start of two refreshes; the heartbeat key expires 15 seconds after the last one.

Three beats per expiry rather than one and a half: a beat that fails or times out still leaves room
for the next one to write the key before the current one expires.
"""

RETRY_BACKOFF_FRACTION = 0.2
"""Fraction of an interval to wait after a failed beat, rather than the full interval."""

STOP_POLL_SECONDS = 1.0
"""Longest the thread sleeps before checking for a stop request, which bounds shutdown latency."""

THREAD_NAME = "infrahub-heartbeat"

CacheFactory = Callable[[], Awaitable[InfrahubCache]]


async def build_heartbeat_cache() -> InfrahubCache:
    """Open the cache connection the heartbeat thread writes through.

    Must be awaited on the heartbeat thread's own event loop: the asyncio cache clients bind to the
    loop that creates them, so the main-loop connection cannot be reused from the thread.
    """
    return config.OVERRIDE.cache or await InfrahubCache.new_from_driver(driver=config.SETTINGS.cache.driver)


class WorkerHeartbeat:
    """Publish this worker's liveness from a dedicated thread running its own event loop.

    The heartbeat key expires 15 seconds after its last refresh, and it is the only thing that
    protects a distributed lock a live worker holds: the deadlock cleanup deletes any old lock whose
    holder has left the active-worker set. An asyncio schedule on the main loop cannot promise that
    refresh, because a CPU-bound stretch in a flow (no ``await`` for tens of seconds) starves every
    other task on that loop, so the worker looks dead while it is merely busy. A thread stays
    independent of the main loop; a pure-Python stall still releases the interpreter lock every few
    milliseconds, which is all the refresh needs.

    The thread opens its own cache connection (see ``build_heartbeat_cache``). A beat that fails
    closes that connection and the next beat opens a fresh one through the factory, so a cache
    outage delays the heartbeat instead of ending it, and a client left broken by the outage is
    never retried forever.

    Each beat is bounded by ``beat_timeout_seconds`` and the next one is scheduled from before the
    current one starts, so the key is rewritten once per interval rather than once per interval plus
    however long the beat took. The bound matters because the cache clients do not impose one: a
    connection that stops answering without closing (a load balancer dropping an idle connection, a
    failover without an RST) would otherwise block the beat indefinitely, and ``stop`` cannot end a
    thread that is inside such a call.
    """

    def __init__(
        self,
        component_type: ComponentType,
        cache_factory: CacheFactory,
        interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
        log: InfrahubLogger | None = None,
    ) -> None:
        self.component_type = component_type
        self.cache_factory = cache_factory
        self.interval_seconds = interval_seconds
        self.beat_timeout_seconds = interval_seconds
        self.retry_backoff_seconds = interval_seconds * RETRY_BACKOFF_FRACTION
        self.log = log or get_logger()
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the heartbeat thread.

        A no-op while a thread is alive, including one still finishing after a ``stop`` whose wait
        timed out: that thread keeps its stop request and exits on its own, and a second one started
        beside it would be a heartbeat nothing could stop through this object.
        """
        if self.running:
            return
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self._run, name=THREAD_NAME, daemon=True)
        self._thread.start()

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Ask the thread to exit and wait for it.

        The thread notices the request within ``STOP_POLL_SECONDS`` and closes its cache connection
        before exiting, so the wait normally ends well inside ``timeout_seconds``. This blocks the
        calling thread; from a coroutine, run it with ``asyncio.to_thread``.

        If the thread is still alive when the wait ends, typically because a cache call has not
        returned yet, the reference to it is kept so that ``running`` stays truthful and ``start``
        cannot spawn a duplicate; the thread exits as soon as that call returns.

        Args:
            timeout_seconds: Longest to wait for the thread to exit.

        """
        self._stop_requested.set()
        if self._thread is None:
            return
        self._thread.join(timeout=timeout_seconds)
        if self._thread.is_alive():
            self.log.warning(
                "Worker heartbeat thread still running after the stop timeout", timeout_seconds=timeout_seconds
            )
            return
        self._thread = None

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._beat_until_stopped())
        finally:
            loop.close()

    async def _beat_until_stopped(self) -> None:
        cache: InfrahubCache | None = None
        try:
            while not self._stop_requested.is_set():
                # Anchored before the beat, so a slow beat eats into the interval instead of adding to
                # it and pushing the next write past the key's expiry.
                deadline = time.monotonic() + self.interval_seconds
                try:
                    if cache is None:
                        cache = await asyncio.wait_for(self.cache_factory(), timeout=self.beat_timeout_seconds)
                    await asyncio.wait_for(
                        refresh_worker_heartbeat(cache=cache, component_type=self.component_type),
                        timeout=self.beat_timeout_seconds,
                    )
                # Top-level boundary of the thread: a beat that fails or times out leaves the heartbeat
                # running, and abandons its connection because a cancelled command can leave a response
                # unread on it.
                except Exception:
                    self.log.exception("Worker heartbeat refresh failed")
                    if cache is not None:
                        await self._close_quietly(cache=cache)
                        cache = None
                    deadline = time.monotonic() + self.retry_backoff_seconds
                await self._sleep_until(deadline=deadline)
        finally:
            if cache is not None:
                await self._close_quietly(cache=cache)

    async def _close_quietly(self, cache: InfrahubCache) -> None:
        try:
            await cache.close_connection()
        # A client that just failed a refresh may fail to close as well; the connection is being
        # abandoned either way, so this is logged rather than allowed to end the thread.
        except Exception:
            self.log.exception("Worker heartbeat cache connection could not be closed")

    async def _sleep_until(self, deadline: float) -> None:
        while not self._stop_requested.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, STOP_POLL_SECONDS))
