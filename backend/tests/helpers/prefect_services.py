"""Drain Prefect's background queue services when the test process changes Prefect server.

Prefect routes events and API logs through process-wide queue services that are created once and
pin to the API URL in effect when they first start; a later change of URL does not rebind them. A
test process that talks to more than one Prefect server would otherwise keep sending to the first.
Draining unpins them, and it has to happen on both sides of a server change: on the way in, while
the previous URL still resolves, so already-queued items reach the server they were meant for; and
on the way out, before the new server is torn down. After a drain, the next event starts a fresh
service against the current URL.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import TYPE_CHECKING

from prefect.events.worker import EventsWorker
from prefect.logging.handlers import APILogWorker
from prefect.settings import PREFECT_API_URL, temporary_settings

if TYPE_CHECKING:
    from collections.abc import Generator

# Upper bound on how long the queue services are given to flush what they still hold. A drain
# against a live server is quick; the ceiling is there for one against a server that has gone
# away, where closing the events websocket waits on a close handshake that will never come.
DRAIN_TIMEOUT_SECONDS = 10.0

# Prefect registers every queue service in one dict on their shared base class, so draining
# through one subclass already drains the other. Both are named anyway: the registry being shared
# is an implementation detail of the pinned version, and this stays correct if a later one gives
# each subclass a registry of its own.
_QUEUE_SERVICES = (EventsWorker, APILogWorker)


def drain_prefect_queue_services(timeout: float = DRAIN_TIMEOUT_SECONDS) -> None:
    """Stop Prefect's queue services and wait for the work they still hold.

    A drain that hits the timeout still rebinds — ``_stop`` unregisters the instance before any
    waiting — it just leaves items unflushed. It also announces itself: the service logs
    ``Still processing items: N items remaining`` every few seconds while a drain is pending, so
    a slow one is already visible in the test output without anything reported from here.

    Args:
        timeout: Seconds to wait for the services to flush before giving up on them.

    Raises:
        RuntimeError: When called from a coroutine, where ``drain_all`` returns an awaitable this
            function cannot wait on.

    """
    if _running_loop() is not None:
        raise RuntimeError(
            "drain_prefect_queue_services() only works outside the event loop; from a coroutine, "
            "await EventsWorker.drain_all() instead."
        )

    for service in _QUEUE_SERVICES:
        service.drain_all(timeout=timeout)


@contextmanager
def prefect_api_target(server_api_url: str) -> Generator[str, None, None]:
    """Point Prefect at ``server_api_url`` for the duration of the block.

    Both the setting and the queue services follow, so events and logs emitted inside the block
    reach the server the block names.
    """
    drain_prefect_queue_services()
    with temporary_settings(updates={PREFECT_API_URL: server_api_url}):
        try:
            yield server_api_url
        finally:
            drain_prefect_queue_services()


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None
