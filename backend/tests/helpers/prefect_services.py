"""Rebind Prefect's background queue services when the test process changes Prefect server.

Prefect emits events and API logs through process-wide background services, ``EventsWorker`` and
``APILogWorker``. ``EventsWorker.instance()`` is memoized on ``(client_type, client_options)``,
and for a self-hosted server the options are empty, so the key carries no API URL. The worker it
hands back built its websocket client and its orchestration client once, from whatever
``PREFECT_API_URL`` was set the first time an event was emitted.

A test process talks to more than one Prefect server: an ephemeral one for the whole session, plus
a container that modules and classes opt into. Every orchestration client a test builds follows
the current setting; the queue services do not. So from the second server onwards the events go to
the previous one — silently, while that server is still up, and then as a wall of ``Service
'EventsWorker' failed to process item`` once it has been torn down. Either way the events the
current server's automations and the tests that assert on them are waiting for never arrive.

Draining is what unpins them: ``_stop`` unregisters an instance synchronously, so the next event
builds a new worker against the URL current at that point. Drain on both sides of a change of
server — on the way in, while the old URL still resolves, so queued items reach the server they
were meant for, and on the way out, before the new server is torn down.
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
