from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import sqlalchemy as sa
from prefect.server.events.filters import EventOccurredFilter, EventOrder
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage import INTERACTIVE_PAGE_SIZE
from prefect.server.events.storage.database import raw_count_events, read_events

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from prefect.server.database.orm_models import ORMEvent
    from prefect.server.events.filters import EventFilter
    from sqlalchemy.ext.asyncio import AsyncSession

NEWEST_FIRST_WINDOWS = (timedelta(hours=1), timedelta(days=1), timedelta(days=7), timedelta(days=30))

# Steps from one event type to the next through the index on the event type, instead of reading every event.
_STORED_EVENT_TYPES = sa.text(
    """
    WITH RECURSIVE event_types(event) AS (
        SELECT min(event) FROM events
        UNION ALL
        SELECT (SELECT min(events.event) FROM events WHERE events.event > event_types.event)
        FROM event_types
        WHERE event_types.event IS NOT NULL
    )
    SELECT event FROM event_types WHERE event IS NOT NULL
    """
)


async def read_stored_event_types(session: AsyncSession) -> list[str]:
    """Return each event type stored in the task manager's database once."""
    return list((await session.scalars(_STORED_EVENT_TYPES)).all())


def _between(filter: EventFilter, since: datetime, until: datetime) -> EventFilter:
    return filter.model_copy(update={"occurred": EventOccurredFilter(since=since, until=until)})


async def _read_page(
    session: AsyncSession, filter: EventFilter, since: datetime, page_size: int, offset: int | None
) -> Sequence[ORMEvent]:
    between = _between(filter=filter, since=since, until=filter.occurred.until)
    return await read_events(session, between, limit=page_size, offset=offset)  # type: ignore[attr-defined]


async def _read_newest_first(
    session: AsyncSession, filter: EventFilter, since: datetime, page_size: int, offset: int | None
) -> Sequence[ORMEvent]:
    """Read the page from the most recent window that holds it, widening up to the whole range."""
    until = filter.occurred.until
    page_limit = max(0, min(page_size, filter.logical_limit))
    for window in NEWEST_FIRST_WINDOWS:
        if until - window <= since:
            break
        page = await _read_page(
            session=session, filter=filter, since=until - window, page_size=page_size, offset=offset
        )
        # A window holding the offset and a full page holds the newest matches of the whole range.
        if len(page) >= page_limit:
            return page
    return await _read_page(session=session, filter=filter, since=since, page_size=page_size, offset=offset)


async def query_events(
    session: AsyncSession,
    filter: EventFilter,
    retention: timedelta,
    page_size: int = INTERACTIVE_PAGE_SIZE,
    offset: int | None = None,
    include_total: bool = True,
) -> tuple[list[ReceivedEvent], int | None]:
    """Read a page of events from the filter's start, or the retention back from its end when it sets no start."""
    until = filter.occurred.until
    since = filter.occurred.since if "since" in filter.occurred.model_fields_set else until - retention
    if filter.order == EventOrder.DESC:
        page = await _read_newest_first(session=session, filter=filter, since=since, page_size=page_size, offset=offset)
    else:
        page = await _read_page(session=session, filter=filter, since=since, page_size=page_size, offset=offset)
    count = None
    if include_total:
        count = await raw_count_events(session, _between(filter=filter, since=since, until=until))  # type: ignore[attr-defined]
    events = [ReceivedEvent.model_validate(event, from_attributes=True) for event in page]
    return events, count
