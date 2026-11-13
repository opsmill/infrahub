from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from prefect.exceptions import PrefectHTTPStatusError
from structlog.testing import capture_logs

from infrahub.events.constants import EventSortOrder
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


def _event_id(number: int) -> str:
    return f"00000000-0000-0000-0000-{number:012d}"


def _stored_event(number: int, second: int) -> dict[str, Any]:
    return {
        "id": _event_id(number),
        "event": "infrahub.node.updated",
        "occurred": f"2026-10-04T12:00:{second:02d}Z",
        "resource": {"prefect.resource.id": "infrahub.node.n1"},
    }


def _page(events: list[dict[str, Any]], total: int | None) -> httpx.Response:
    return httpx.Response(status_code=200, json={"events": events, "total": total})


@dataclass
class MergedPageCase:
    name: str
    order: EventSortOrder
    pages: list[list[dict[str, Any]]]
    expected: list[int]


MERGED_PAGE_CASES = [
    MergedPageCase(
        name="newest_first",
        order=EventSortOrder.DESC,
        pages=[
            [_stored_event(number=5, second=3), _stored_event(number=1, second=1)],
            [_stored_event(number=4, second=3), _stored_event(number=3, second=2)],
        ],
        expected=[4, 3],
    ),
    MergedPageCase(
        name="oldest_first",
        order=EventSortOrder.ASC,
        pages=[
            [_stored_event(number=1, second=1), _stored_event(number=5, second=3)],
            [_stored_event(number=3, second=2), _stored_event(number=4, second=3)],
        ],
        expected=[3, 4],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in MERGED_PAGE_CASES])
async def test_the_pages_of_two_filters_are_merged_by_time_then_id(test_case: MergedPageCase) -> None:
    """Each filter is asked for its events up to the end of the page, and the offset is applied to the merged events."""
    filters = InfrahubEventFilter.from_filters(order=test_case.order).for_primary_nodes(primary_node__ids=["n1"])
    task_manager = ScriptedTaskManager(
        responses=[_page(events=test_case.pages[0], total=5), _page(events=test_case.pages[1], total=2)]
    )

    async with task_manager.client() as client:
        response = await PrefectEvent.query_merged_events(
            client=client, limit=2, filters=filters, offset=1, include_total=True
        )

    assert [str(event.id) for event in response.events] == [_event_id(number) for number in test_case.expected]
    assert response.count == 7
    assert [
        (request.path, request.body["limit"], request.body["offset"], request.body["include_total"])
        for request in task_manager.requests
    ] == [(EVENTS_FILTER_PATH, 3, None, True)] * 2
    assert sorted((request.body["filter"]["event"] for request in task_manager.requests), key=str) == sorted(
        (event_filter.to_request()["event"] for event_filter in filters), key=str
    )


async def test_one_filter_is_read_with_the_offset_of_the_page() -> None:
    """A single filter is sent once, with the limit and the offset of the page, and its count is returned as it is."""
    task_manager = ScriptedTaskManager(responses=[_page(events=[_stored_event(number=1, second=1)], total=None)])

    async with task_manager.client() as client:
        response = await PrefectEvent.query_merged_events(
            client=client, limit=2, filters=[InfrahubEventFilter()], offset=4, include_total=False
        )

    assert ([str(event.id) for event in response.events], response.count) == ([_event_id(1)], None)
    assert [
        (request.path, request.body["limit"], request.body["offset"], request.body["include_total"])
        for request in task_manager.requests
    ] == [(EVENTS_FILTER_PATH, 2, 4, False)]
