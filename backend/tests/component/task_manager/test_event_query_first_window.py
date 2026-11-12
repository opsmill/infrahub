from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from prefect.server.events.filters import EventNameFilter
from prefect.server.events.schemas.events import ReceivedEvent, Resource
from prefect.server.events.storage.database import write_events
from sqlalchemy import event as sqlalchemy_event

from infrahub.prefect_server.database import query_events
from infrahub.prefect_server.models import InfrahubEventFilter

if TYPE_CHECKING:
    from prefect.server.database import PrefectDBInterface
    from sqlalchemy.orm import ORMExecuteState

RETENTION = timedelta(days=365)
NODE_UPDATED = "infrahub.node.updated"
BRANCH_MERGED = "infrahub.branch.merged"
FLOW_RUN_COMPLETED = "prefect.flow-run.Completed"
# Every Infrahub event is older than the widest time window, and the only newer event is one of Prefect's own.
STORED_EVENTS = [
    (FLOW_RUN_COMPLETED, timedelta(minutes=1)),
    (NODE_UPDATED, timedelta(days=40)),
    (NODE_UPDATED, timedelta(days=40, minutes=1)),
    (NODE_UPDATED, timedelta(days=41)),
]


@pytest.fixture
async def stored_event_ids(database: PrefectDBInterface) -> list[UUID]:
    """IDs of the stored events, newest first."""
    now = datetime.now(UTC)
    events = [
        ReceivedEvent(
            id=uuid4(),
            occurred=now - age,
            event=event_type,
            resource=Resource({"prefect.resource.id": f"test.{uuid4()}"}),
        )
        for event_type, age in STORED_EVENTS
    ]
    async with database.session_context(begin_transaction=True) as session:
        await write_events(session=session, events=events)
    return [event.id for event in events]


@dataclass
class FirstWindowCase:
    name: str
    event_types: list[str] | None
    expected_events: list[int]
    expected_statements: int


FIRST_WINDOW_CASES = [
    FirstWindowCase(
        name="newest_infrahub_events_older_than_every_window",
        event_types=None,
        expected_events=[1, 2],
        expected_statements=2,
    ),
    FirstWindowCase(
        name="no_event_of_the_listed_event_types",
        event_types=[BRANCH_MERGED],
        expected_events=[],
        expected_statements=1,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FIRST_WINDOW_CASES])
async def test_the_first_window_ends_at_the_newest_event_of_the_requested_event_types(
    test_case: FirstWindowCase, database: PrefectDBInterface, stored_event_ids: list[UUID]
) -> None:
    """The page is read after one read of the newest event's time: in one window when that window fills it, in none when there is no event."""
    event_filter = InfrahubEventFilter.default()
    if test_case.event_types:
        event_filter.event = EventNameFilter(
            prefix=None, name=test_case.event_types, exclude_prefix=None, exclude_name=None
        )
    event_filter.set_prefix()
    statements: list[ORMExecuteState] = []

    async with database.session_context() as session:
        sqlalchemy_event.listen(session.sync_session, "do_orm_execute", statements.append)
        events, total = await query_events(
            session=session, filter=event_filter, retention=RETENTION, page_size=2, include_total=False
        )

    assert [event.id for event in events] == [stored_event_ids[index] for index in test_case.expected_events]
    assert total is None
    assert len(statements) == test_case.expected_statements
