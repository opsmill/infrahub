"""Tests for the Prefect queue service rebinding in tests.helpers.prefect_services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect._internal.concurrency.services import QueueService
from prefect.settings import PREFECT_API_URL, get_current_settings, temporary_settings

from tests.helpers.prefect_services import drain_prefect_queue_services, prefect_api_target

if TYPE_CHECKING:
    from collections.abc import Generator

SERVER_A = "http://localhost:14200/api"
SERVER_B = "http://localhost:14201/api"


class StubQueueService(QueueService[int]):
    """Stands in for EventsWorker and APILogWorker, which need a live server to start.

    Prefect keeps every queue service in one registry, so this is drained by the same call.
    """

    async def _handle(self, item: int) -> None:
        return None


@pytest.fixture(autouse=True)
def no_leftover_services() -> Generator[None, None, None]:
    drain_prefect_queue_services()
    yield
    drain_prefect_queue_services()


def test_prefect_api_target_points_prefect_at_the_server_and_restores_it() -> None:
    with temporary_settings(updates={PREFECT_API_URL: SERVER_A}):
        with prefect_api_target(SERVER_B) as target:
            assert target == SERVER_B
            assert get_current_settings().api.url == SERVER_B

        assert get_current_settings().api.url == SERVER_A


def test_entering_a_target_unpins_a_service_bound_to_the_previous_server() -> None:
    """A service started against one server must not be reused against the next one.

    `EventsWorker.instance()` is memoized on a key that holds no API URL, and the clients it
    builds read `PREFECT_API_URL` once, so without this every event after the first change of
    server is emitted at the server the process has moved off.
    """
    with temporary_settings(updates={PREFECT_API_URL: SERVER_A}):
        bound_to_a = StubQueueService.instance()

        with prefect_api_target(SERVER_B):
            assert StubQueueService.instance() is not bound_to_a


def test_leaving_a_target_unpins_a_service_bound_to_it() -> None:
    with temporary_settings(updates={PREFECT_API_URL: SERVER_A}):
        with prefect_api_target(SERVER_B):
            bound_to_b = StubQueueService.instance()

        assert StubQueueService.instance() is not bound_to_b


def test_a_service_is_reused_while_the_server_does_not_change() -> None:
    with temporary_settings(updates={PREFECT_API_URL: SERVER_A}), prefect_api_target(SERVER_B):
        assert StubQueueService.instance() is StubQueueService.instance()


def test_draining_hands_over_the_items_a_service_still_holds() -> None:
    """The drain has to flush, not just unregister: it runs while the old server is still up."""
    handled: list[int] = []

    class RecordingQueueService(QueueService[int]):
        async def _handle(self, item: int) -> None:
            handled.append(item)

    service = RecordingQueueService.instance()
    for item in range(10):
        service.send(item)

    drain_prefect_queue_services()

    assert handled == list(range(10))


async def test_draining_from_a_coroutine_is_refused() -> None:
    with pytest.raises(RuntimeError, match="outside the event loop"):
        drain_prefect_queue_services()
