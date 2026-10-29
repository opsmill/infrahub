from __future__ import annotations

import httpx
import pytest
from prefect.exceptions import PrefectHTTPStatusError
from structlog.testing import capture_logs

from infrahub.exceptions import ServiceUnavailableError
from infrahub.task_manager.event.models import InfrahubEventFilter
from infrahub.task_manager.event.query import PrefectEvent, PrefectEventResponse
from tests.helpers.task_history_api import ScriptedTaskManager

EVENTS_FILTER_PATH = "/api/infrahub/events/filter"


def _failed(status_code: int, detail: str) -> httpx.Response:
    return httpx.Response(status_code=status_code, json={"detail": detail})


def _empty_page() -> httpx.Response:
    return httpx.Response(status_code=200, json={"events": [], "total": 0})


async def _query(task_manager: ScriptedTaskManager) -> PrefectEventResponse:
    async with task_manager.client() as client:
        return await PrefectEvent.query_events(client=client, limit=1, filters=InfrahubEventFilter())


async def test_a_refused_event_query_fails_without_a_retry() -> None:
    """A 4xx answer is the same on every attempt, so the query is sent once and the answer is logged once."""
    task_manager = ScriptedTaskManager(responses=[_failed(status_code=422, detail="limit must be positive")])

    with capture_logs() as records, pytest.raises(ServiceUnavailableError, match=r"\(status_code=422\)$") as raised:
        await _query(task_manager=task_manager)

    assert [request.path for request in task_manager.requests] == [EVENTS_FILTER_PATH]
    assert raised.value.message == "Unable to query prefect due to invalid response from the server (status_code=422)"
    assert isinstance(raised.value.__cause__, PrefectHTTPStatusError)
    assert records == [
        {
            "event": "Event query to the task manager failed",
            "attempts": 1,
            "status_code": 422,
            "error": (
                "Client error '422 Unprocessable Entity' for url 'http://task-manager:4200/api/infrahub/events/filter'"
                " - Response: {'detail': 'limit must be positive'}"
                " - For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/422"
            ),
            "log_level": "warning",
        }
    ]


async def test_a_server_error_is_retried_and_only_the_last_attempt_says_it_failed() -> None:
    """A 5xx answer is sent up to four times, and the last failed attempt is logged as the failure, not as a retry."""
    task_manager = ScriptedTaskManager(
        responses=[_failed(status_code=500, detail="database timeout") for _ in range(4)]
    )

    with capture_logs() as records, pytest.raises(ServiceUnavailableError, match=r"\(status_code=500\)$") as raised:
        await _query(task_manager=task_manager)

    assert [request.path for request in task_manager.requests] == [EVENTS_FILTER_PATH] * 4
    assert raised.value.message == "Unable to query prefect due to invalid response from the server (status_code=500)"
    assert isinstance(raised.value.__cause__, PrefectHTTPStatusError)
    assert records == [
        {
            "event": "Event query to the task manager failed, retrying",
            "attempt": attempt,
            "status_code": 500,
            "log_level": "warning",
        }
        for attempt in (1, 2, 3)
    ] + [
        {
            "event": "Event query to the task manager failed",
            "attempts": 4,
            "status_code": 500,
            "error": (
                "Server error '500 Internal Server Error' for url 'http://task-manager:4200/api/infrahub/events/filter'"
                " - Response: {'detail': 'database timeout'}"
                " - For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500"
            ),
            "log_level": "warning",
        }
    ]


async def test_an_event_query_answered_after_a_server_error_returns_the_page() -> None:
    """A query answered on its second attempt returns that answer, with one retry logged."""
    task_manager = ScriptedTaskManager(responses=[_failed(status_code=500, detail="database timeout"), _empty_page()])

    with capture_logs() as records:
        response = await _query(task_manager=task_manager)

    assert [request.path for request in task_manager.requests] == [EVENTS_FILTER_PATH] * 2
    assert (response.count, response.events) == (0, [])
    assert records == [
        {
            "event": "Event query to the task manager failed, retrying",
            "attempt": 1,
            "status_code": 500,
            "log_level": "warning",
        }
    ]
