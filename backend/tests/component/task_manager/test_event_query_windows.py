from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.server.database import provide_database_interface
from prefect.server.events.filters import EventFilter as StoredEventFilter
from prefect.server.events.storage.database import read_events
from tests.helpers.event_filters import filter_event_ids, filter_events
from tests.helpers.task_manager_seed import seed_infrahub_event

from infrahub.core.changelog.models import NodeChangelog
from infrahub.events.constants import EventSortOrder
from infrahub.events.models import EventBranchContext, EventContext, EventMeta
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.task_manager.event.models import InfrahubEventFilter

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

DENSE_ACCOUNT = str(uuid4())
SPARSE_ACCOUNT = str(uuid4())
BRANCH_ID = str(uuid4())

DENSE_AGES = [timedelta(minutes=4 * index + 1) for index in range(12)] + [
    timedelta(hours=3),
    timedelta(days=2),
    timedelta(days=10),
    timedelta(days=40),
    timedelta(days=200),
    timedelta(days=300),
]
SPARSE_AGES = [
    timedelta(hours=2),
    timedelta(days=3),
    timedelta(days=20),
    timedelta(days=100),
    timedelta(days=200),
    timedelta(days=300),
]


@dataclass
class Seeded:
    now: datetime
    dense: list[str]
    sparse: list[str]

    def account_events(self, account: str) -> list[str]:
        return self.dense if account == DENSE_ACCOUNT else self.sparse


def _event(account: str) -> NodeUpdatedEvent:
    node_id = str(uuid4())
    return NodeUpdatedEvent(
        kind="TestingNode",
        node_id=node_id,
        changelog=NodeChangelog(node_id=node_id, node_kind="TestingNode", display_label=node_id),
        fields=["name"],
        meta=EventMeta(context=EventContext(branch=EventBranchContext(name="main", id=BRANCH_ID), account_id=account)),
    )


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture(scope="module")
async def seeded(prefect_client: PrefectClient) -> Seeded:
    """Events of a dense and a sparse account, newest first, each at a time of its own."""
    now = datetime.now(UTC)
    dense = [str(await seed_infrahub_event(event=_event(DENSE_ACCOUNT), occurred=now - age)) for age in DENSE_AGES]
    sparse = [str(await seed_infrahub_event(event=_event(SPARSE_ACCOUNT), occurred=now - age)) for age in SPARSE_AGES]
    return Seeded(now=now, dense=dense, sparse=sparse)


@dataclass
class WindowCase:
    name: str
    account: str
    limit: int
    expected: list[int]
    offset: int | None = None
    retention: timedelta = timedelta(days=400)
    until_age: timedelta | None = None
    since_age: timedelta | None = None
    order: EventSortOrder = EventSortOrder.DESC


WINDOW_CASES = [
    WindowCase(name="dense_first_page", account=DENSE_ACCOUNT, limit=5, expected=[0, 1, 2, 3, 4]),
    WindowCase(
        name="dense_page_past_the_first_window",
        account=DENSE_ACCOUNT,
        limit=5,
        offset=10,
        expected=[10, 11, 12, 13, 14],
    ),
    WindowCase(name="sparse_first_page", account=SPARSE_ACCOUNT, limit=3, expected=[0, 1, 2]),
    WindowCase(
        name="sparse_page_older_than_180_days",
        account=SPARSE_ACCOUNT,
        limit=3,
        offset=3,
        expected=[3, 4, 5],
    ),
    WindowCase(
        name="retention_bounds_the_widest_window",
        account=SPARSE_ACCOUNT,
        limit=10,
        retention=timedelta(days=250),
        expected=[0, 1, 2, 3, 4],
    ),
    WindowCase(
        name="sparse_until_anchored",
        account=SPARSE_ACCOUNT,
        limit=2,
        until_age=timedelta(days=1),
        expected=[1, 2],
    ),
    WindowCase(
        name="dense_until_anchored_with_offset",
        account=DENSE_ACCOUNT,
        limit=3,
        offset=1,
        until_age=timedelta(hours=1),
        expected=[13, 14, 15],
    ),
    WindowCase(
        name="explicit_start",
        account=SPARSE_ACCOUNT,
        limit=10,
        since_age=timedelta(days=150),
        expected=[0, 1, 2, 3],
    ),
    WindowCase(
        name="oldest_first",
        account=SPARSE_ACCOUNT,
        limit=3,
        order=EventSortOrder.ASC,
        expected=[5, 4, 3],
    ),
]


async def _read_once(event_filter: InfrahubEventFilter, since: datetime, limit: int, offset: int | None) -> list[str]:
    stored_filter = StoredEventFilter.model_validate(
        {**event_filter.to_request(), "occurred": {"since": since.isoformat(), "until": event_filter.occurred.until}}
    )
    db = provide_database_interface()
    async with db.session_context() as session:
        events = await read_events(session=session, events_filter=stored_filter, limit=limit, offset=offset)
    return [str(event.id) for event in events]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in WINDOW_CASES])
async def test_windows_return_the_events_of_a_single_read(
    test_case: WindowCase, seeded: Seeded, prefect_client: PrefectClient
) -> None:
    """Reading newest first through widening windows returns the page a single read over the whole range returns."""
    until = seeded.now - test_case.until_age if test_case.until_age else seeded.now
    since = seeded.now - test_case.since_age if test_case.since_age else None
    event_filter = InfrahubEventFilter.from_filters(
        order=test_case.order, account__ids=[test_case.account], since=since, until=until
    )

    page = await filter_event_ids(
        client=prefect_client,
        event_filter=event_filter,
        limit=test_case.limit,
        offset=test_case.offset,
        retention=test_case.retention,
    )

    account_events = seeded.account_events(test_case.account)
    assert page == [account_events[index] for index in test_case.expected]
    assert page == await _read_once(
        event_filter=event_filter,
        since=since or until - test_case.retention,
        limit=test_case.limit,
        offset=test_case.offset,
    )


async def test_task_manager_retention_bounds_the_widest_window_by_default(
    seeded: Seeded, prefect_client: PrefectClient
) -> None:
    """Without a retention in the request, the widest window is the task manager's 7-day event retention."""
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, account__ids=[SPARSE_ACCOUNT])

    page = await filter_event_ids(client=prefect_client, event_filter=event_filter, limit=10)

    assert page == seeded.sparse[:2]


async def test_total_is_counted_over_the_whole_range_only_when_requested(
    seeded: Seeded, prefect_client: PrefectClient
) -> None:
    """The total counts every match up to the retention when requested, and is null otherwise."""
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, account__ids=[SPARSE_ACCOUNT])

    counted = await filter_events(
        client=prefect_client, event_filter=event_filter, limit=1, retention=timedelta(days=400), include_total=True
    )
    not_counted = await filter_events(
        client=prefect_client, event_filter=event_filter, limit=1, retention=timedelta(days=400), include_total=False
    )

    assert [event["id"] for event in counted["events"]] == seeded.sparse[:1]
    assert counted["total"] == 6
    assert [event["id"] for event in not_counted["events"]] == seeded.sparse[:1]
    assert not_counted["total"] is None
