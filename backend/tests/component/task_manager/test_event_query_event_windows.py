from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from prefect.server.events.filters import EventNameFilter, EventOccurredFilter, EventOrder, EventResourceFilter
from prefect.server.events.schemas.events import ReceivedEvent, Resource
from prefect.server.events.storage.database import write_events
from sqlalchemy import event as sqlalchemy_event

from infrahub.prefect_server.database import query_events
from infrahub.prefect_server.models import InfrahubEventFilter

if TYPE_CHECKING:
    from prefect.server.database import PrefectDBInterface
    from sqlalchemy.orm import ORMExecuteState

RETENTION = timedelta(days=365)
WINDOW_EVENT_COUNTS = (3, 5)
NODE_UPDATED = "infrahub.node.updated"
BRANCH_MERGED = "infrahub.branch.merged"
FLOW_RUN_COMPLETED = "prefect.flow-run.Completed"
MATCHING_NODE = "infrahub.node.matching"
OTHER_NODE = "infrahub.node.other"
RARE_NODE = "infrahub.node.rare"
FLOW_RUN = "prefect.flow-run.one"
# Newest first. Windows of 3 and 5 Infrahub events hold events 1 to 3 and events 4 to 9, and events 10 to 15 are the
# rest of the range. Every Infrahub event is 40 days old, and the only newer event is one of Prefect's own.
STORED_EVENTS = [
    (FLOW_RUN_COMPLETED, FLOW_RUN, timedelta(minutes=1)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=1)),
    (NODE_UPDATED, OTHER_NODE, timedelta(days=40, minutes=2)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=3)),
    (NODE_UPDATED, OTHER_NODE, timedelta(days=40, minutes=4)),
    (FLOW_RUN_COMPLETED, FLOW_RUN, timedelta(days=40, minutes=5)),
    (NODE_UPDATED, OTHER_NODE, timedelta(days=40, minutes=6)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=7)),
    (NODE_UPDATED, OTHER_NODE, timedelta(days=40, minutes=8)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=9)),
    (NODE_UPDATED, OTHER_NODE, timedelta(days=40, minutes=10)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=11)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=12)),
    (NODE_UPDATED, OTHER_NODE, timedelta(days=40, minutes=13)),
    (NODE_UPDATED, MATCHING_NODE, timedelta(days=40, minutes=14)),
    (NODE_UPDATED, RARE_NODE, timedelta(days=40, minutes=15)),
]
# The two events at 3 minutes share a time, and a window of 3 events ends between them.
SAME_TIME_EVENTS = [
    (MATCHING_NODE, timedelta(minutes=1)),
    (OTHER_NODE, timedelta(minutes=2)),
    (MATCHING_NODE, timedelta(minutes=3)),
    (MATCHING_NODE, timedelta(minutes=3)),
    (MATCHING_NODE, timedelta(minutes=4)),
]


@dataclass(frozen=True)
class Stored:
    now: datetime
    ids: list[UUID]


async def _store(database: PrefectDBInterface, events: list[ReceivedEvent]) -> None:
    async with database.session_context(begin_transaction=True) as session:
        await write_events(session=session, events=events)


@pytest.fixture
async def stored(database: PrefectDBInterface) -> Stored:
    """The stored events, newest first."""
    now = datetime.now(UTC)
    events = [
        ReceivedEvent(
            id=uuid4(), occurred=now - age, event=event_type, resource=Resource({"prefect.resource.id": resource})
        )
        for event_type, resource, age in STORED_EVENTS
    ]
    await _store(database=database, events=events)
    return Stored(now=now, ids=[event.id for event in events])


@dataclass
class EventWindowCase:
    name: str
    page_size: int
    expected_events: list[int]
    expected_statements: int
    resources: tuple[str, ...] = (MATCHING_NODE,)
    one_per_resource: bool = False
    event_types: tuple[str, ...] = ()
    offset: int | None = None
    since_age: timedelta | None = None
    order: EventOrder = EventOrder.DESC


EVENT_WINDOW_CASES = [
    EventWindowCase(
        name="page_filled_by_the_first_window",
        page_size=2,
        expected_events=[1, 3],
        expected_statements=2,
    ),
    EventWindowCase(
        name="page_filled_by_the_second_window",
        page_size=3,
        expected_events=[1, 3, 7],
        expected_statements=4,
    ),
    EventWindowCase(
        name="page_filled_by_the_rest_of_the_range",
        page_size=5,
        expected_events=[1, 3, 7, 9, 11],
        expected_statements=5,
    ),
    EventWindowCase(
        name="fewer_matching_events_than_the_page",
        page_size=10,
        expected_events=[1, 3, 7, 9, 11, 12, 14],
        expected_statements=5,
    ),
    EventWindowCase(
        name="matching_event_only_in_the_rest_of_the_range",
        page_size=1,
        resources=(RARE_NODE,),
        expected_events=[15],
        expected_statements=5,
    ),
    EventWindowCase(
        name="offset_inside_the_first_window",
        page_size=2,
        offset=1,
        expected_events=[3, 7],
        expected_statements=4,
    ),
    EventWindowCase(
        name="offset_past_the_first_window",
        page_size=2,
        offset=3,
        expected_events=[9, 11],
        expected_statements=5,
    ),
    EventWindowCase(
        name="offset_past_the_second_window",
        page_size=5,
        offset=5,
        expected_events=[12, 14],
        expected_statements=5,
    ),
    EventWindowCase(
        name="one_event_per_resource",
        page_size=2,
        resources=(MATCHING_NODE, RARE_NODE),
        one_per_resource=True,
        expected_events=[1, 15],
        expected_statements=5,
    ),
    EventWindowCase(
        name="range_with_fewer_events_than_the_second_window",
        page_size=10,
        since_age=timedelta(days=40, minutes=7, seconds=30),
        expected_events=[1, 3, 7],
        expected_statements=4,
    ),
    EventWindowCase(
        name="range_that_starts_at_the_oldest_event_of_the_second_window",
        page_size=10,
        since_age=timedelta(days=40, minutes=9),
        expected_events=[1, 3, 7, 9],
        expected_statements=4,
    ),
    EventWindowCase(
        name="no_event_of_the_listed_event_types",
        page_size=2,
        resources=(),
        event_types=(BRANCH_MERGED,),
        expected_events=[],
        expected_statements=1,
    ),
    EventWindowCase(
        name="oldest_first",
        page_size=3,
        order=EventOrder.ASC,
        expected_events=[14, 12, 11],
        expected_statements=1,
    ),
]


async def _read_page(
    database: PrefectDBInterface, event_filter: InfrahubEventFilter, page_size: int, offset: int | None = None
) -> tuple[list[UUID], int]:
    """Return the IDs of the page read through the small windows, and the number of statements the read ran."""
    statements: list[ORMExecuteState] = []
    async with database.session_context() as session:
        sqlalchemy_event.listen(session.sync_session, "do_orm_execute", statements.append)
        events, total = await query_events(
            session=session,
            filter=event_filter,
            retention=RETENTION,
            page_size=page_size,
            offset=offset,
            include_total=False,
            window_event_counts=WINDOW_EVENT_COUNTS,
        )
    assert total is None
    return [event.id for event in events], len(statements)


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EVENT_WINDOW_CASES])
async def test_a_newest_first_page_is_read_one_window_of_events_at_a_time(
    test_case: EventWindowCase, database: PrefectDBInterface, stored: Stored
) -> None:
    """The page is read in windows that hold a number of Infrahub events, and no further than the window that fills it."""
    event_filter = InfrahubEventFilter.default()
    event_filter.order = test_case.order
    if test_case.event_types:
        event_filter.event = EventNameFilter(
            prefix=None, name=list(test_case.event_types), exclude_prefix=None, exclude_name=None
        )
    event_filter.set_prefix()
    if test_case.resources:
        event_filter.resource = EventResourceFilter(
            id=list(test_case.resources), id_prefix=None, labels=None, distinct=test_case.one_per_resource
        )
    if test_case.since_age:
        event_filter.occurred = EventOccurredFilter(since=stored.now - test_case.since_age, until=stored.now)

    page, statements = await _read_page(
        database=database, event_filter=event_filter, page_size=test_case.page_size, offset=test_case.offset
    )

    assert page == [stored.ids[index] for index in test_case.expected_events]
    assert statements == test_case.expected_statements


async def test_events_at_the_time_a_window_ends_are_read_once(database: PrefectDBInterface) -> None:
    """Events that share the time of the oldest event of a window are read with that window, and not with the next."""
    now = datetime.now(UTC)
    events = [
        ReceivedEvent(
            id=uuid4(), occurred=now - age, event=NODE_UPDATED, resource=Resource({"prefect.resource.id": resource})
        )
        for resource, age in SAME_TIME_EVENTS
    ]
    await _store(database=database, events=events)
    event_filter = InfrahubEventFilter.default()
    event_filter.set_prefix()
    event_filter.resource = EventResourceFilter(id=[MATCHING_NODE], id_prefix=None, labels=None, distinct=False)

    page, statements = await _read_page(database=database, event_filter=event_filter, page_size=10)

    same_time = sorted((events[2].id, events[3].id), reverse=True)
    assert page == [events[0].id, *same_time, events[4].id]
    assert statements == 4
