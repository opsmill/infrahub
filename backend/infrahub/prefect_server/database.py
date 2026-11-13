from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import sqlalchemy as sa
from prefect.server.database.orm_models import Event
from prefect.server.events.filters import EventOccurredFilter, EventOrder
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage import INTERACTIVE_PAGE_SIZE
from prefect.server.events.storage.database import raw_count_events, read_events

from .models import InfrahubDatabaseVersion

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def earlier_by(moment: datetime, duration: timedelta) -> datetime:
    """Return the UTC time `duration` before `moment`, or the earliest UTC time a datetime holds when that is earlier."""
    earliest = datetime.min.replace(tzinfo=UTC)
    if moment - earliest <= duration:
        return earliest
    return moment.astimezone(UTC) - duration


def newest_first_ranges(since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
    """Split the range into the windows read newest first, each ending just before the newer one starts."""
    ranges: list[tuple[datetime, datetime]] = []
    range_until = until
    for window in NEWEST_FIRST_WINDOWS:
        window_start = earlier_by(moment=until, duration=window)
        if window_start <= since:
            break
        ranges.append((window_start, range_until))
        range_until = window_start - timedelta(microseconds=1)
    ranges.append((since, range_until))
    return ranges


async def _read_page(
    session: AsyncSession, filter: EventFilter, since: datetime, until: datetime, page_size: int, offset: int | None
) -> Sequence[Event]:
    between = _between(filter=filter, since=since, until=until)
    if between.resource and between.resource.distinct:
        return await read_events(session, between, limit=page_size, offset=offset)  # type: ignore[attr-defined]
    order = sa.desc if between.order == EventOrder.DESC else sa.asc
    # The ID orders the events of one time, so an offset skips the same events in every request.
    statement = (
        sa.select(Event)
        .where(*between.build_where_clauses())
        .order_by(order(Event.occurred), order(Event.id))
        .limit(max(0, min(page_size, between.logical_limit)))
    )
    if offset is not None:
        statement = statement.offset(offset)
    return (await session.scalars(statement)).all()


async def _newest_event_time(session: AsyncSession, filter: EventFilter, since: datetime) -> datetime | None:
    """Return the time of the newest event in the filter's range that has one of its event types, if any."""
    conditions = [Event.occurred >= since, Event.occurred <= filter.occurred.until]
    if filter.event:
        conditions.extend(filter.event.build_where_clauses())
    return await session.scalar(sa.select(sa.func.max(Event.occurred)).where(*conditions))


async def _read_newest_first(
    session: AsyncSession, filter: EventFilter, since: datetime, page_size: int, offset: int | None
) -> Sequence[Event]:
    """Read the page newest first, one window at a time, until the windows read so far fill it.

    The windows are counted back from the newest event of the filter's event types, not from the end of the range, so
    the first window holds events however old the newest one is.
    """
    until = await _newest_event_time(session=session, filter=filter, since=since)
    if until is None:
        return []
    page_limit = max(0, min(page_size, filter.logical_limit))
    one_per_resource = bool(filter.resource and filter.resource.distinct)
    # An offset and the one event kept per resource are counted from `until`, so such a read starts there.
    from_until = bool(offset) or one_per_resource
    page: list[Event] = []
    for range_since, range_until in newest_first_ranges(since=since, until=until):
        if from_until:
            rows = await _read_page(
                session=session, filter=filter, since=range_since, until=until, page_size=page_size, offset=offset
            )
            page = list(rows)
            # Once a read returns the events past the offset, the older windows hold only the events after them.
            from_until = one_per_resource or not rows
        else:
            rows = await _read_page(
                session=session, filter=filter, since=range_since, until=range_until, page_size=page_size, offset=None
            )
            page.extend(rows)
        if len(page) >= page_limit:
            return page[:page_limit]
    return page


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
    if "since" in filter.occurred.model_fields_set:
        since: datetime = filter.occurred.since
    else:
        since = earlier_by(moment=until, duration=retention)
    if filter.order == EventOrder.DESC:
        page = await _read_newest_first(session=session, filter=filter, since=since, page_size=page_size, offset=offset)
    else:
        page = await _read_page(
            session=session, filter=filter, since=since, until=until, page_size=page_size, offset=offset
        )
    count = None
    if include_total:
        count = await raw_count_events(session, _between(filter=filter, since=since, until=until))  # type: ignore[attr-defined]
    events = [ReceivedEvent.model_validate(event, from_attributes=True) for event in page]
    return events, count


async def read_database_version(session: AsyncSession) -> InfrahubDatabaseVersion:
    """Return the type and server version of the database the task manager stores its data in."""
    connection = await session.connection()
    version_info = connection.dialect.server_version_info
    return InfrahubDatabaseVersion(
        type=connection.dialect.name,
        version=".".join(str(part) for part in version_info) if version_info else None,
    )
