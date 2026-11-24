from __future__ import annotations

from dataclasses import dataclass
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

# A window holds a number of events, not a duration, so a first page reads as few events when they are dense as when
# they are sparse.
NEWEST_FIRST_WINDOW_EVENT_COUNTS = (2_000, 48_000)


def _between(filter: EventFilter, since: datetime, until: datetime) -> EventFilter:
    return filter.model_copy(update={"occurred": EventOccurredFilter(since=since, until=until)})


def earlier_by(moment: datetime, duration: timedelta) -> datetime:
    """Return the UTC time `duration` before `moment`, or the earliest UTC time a datetime holds when that is earlier."""
    earliest = datetime.min.replace(tzinfo=UTC)
    if moment - earliest <= duration:
        return earliest
    return moment.astimezone(UTC) - duration


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


@dataclass(frozen=True)
class _NewestEvents:
    oldest: datetime
    newest: datetime
    count: int


async def _newest_events(
    session: AsyncSession, filter: EventFilter, since: datetime, until: datetime, limit: int
) -> _NewestEvents | None:
    """Return the time span and the number of the `limit` newest events of the filter's event types in the range, if any."""
    conditions = [Event.occurred >= since, Event.occurred <= until]
    if filter.event:
        conditions.extend(filter.event.build_where_clauses())
    newest = sa.select(Event.occurred).where(*conditions).order_by(Event.occurred.desc()).limit(limit).subquery()
    oldest_time, newest_time, count = (
        await session.execute(
            sa.select(sa.func.min(newest.c.occurred), sa.func.max(newest.c.occurred), sa.func.count())
        )
    ).one()
    if not count:
        return None
    return _NewestEvents(oldest=oldest_time, newest=newest_time, count=count)


async def _read_newest_first(
    session: AsyncSession,
    filter: EventFilter,
    since: datetime,
    page_size: int,
    offset: int | None,
    window_event_counts: Sequence[int],
) -> Sequence[Event]:
    """Read the page newest first, one window at a time, until the windows read so far fill it.

    Each window holds a number of the newest events of the filter's event types that no window before it holds, and
    the last window holds the rest of the range, so the first window holds events however old the newest one is.
    """
    page_limit = max(0, min(page_size, filter.logical_limit))
    one_per_resource = bool(filter.resource and filter.resource.distinct)
    # An offset and the one event kept per resource are counted from the newest event, so such a read starts there.
    from_newest = bool(offset) or one_per_resource
    page: list[Event] = []
    newest: datetime | None = None
    window_until: datetime = filter.occurred.until
    for event_count in (*window_event_counts, None):
        window_since = since
        range_is_read = True
        if event_count is not None:
            events = await _newest_events(
                session=session, filter=filter, since=since, until=window_until, limit=event_count
            )
            if events is None:
                break
            # No event of these types is newer than the newest one found, so the window ends there.
            window_since, window_until = events.oldest, events.newest
            range_is_read = events.count < event_count or window_since <= since
        if newest is None:
            newest = window_until
        if from_newest:
            rows = await _read_page(
                session=session, filter=filter, since=window_since, until=newest, page_size=page_size, offset=offset
            )
            page = list(rows)
            # Once a read returns the events past the offset, the older windows hold only the events after them.
            from_newest = one_per_resource or not rows
        else:
            rows = await _read_page(
                session=session,
                filter=filter,
                since=window_since,
                until=window_until,
                page_size=page_size,
                offset=None,
            )
            page.extend(rows)
        if range_is_read or len(page) >= page_limit:
            break
        window_until = window_since - timedelta(microseconds=1)
    return page[:page_limit]


async def query_events(
    session: AsyncSession,
    filter: EventFilter,
    retention: timedelta,
    page_size: int = INTERACTIVE_PAGE_SIZE,
    offset: int | None = None,
    include_total: bool = True,
    window_event_counts: Sequence[int] = NEWEST_FIRST_WINDOW_EVENT_COUNTS,
) -> tuple[list[ReceivedEvent], int | None]:
    """Read a page of events from the filter's start, or the retention back from its end when it sets no start.

    Args:
        window_event_counts: Number of events in each window that a newest-first read tries before the rest of the
            range.

    """
    until = filter.occurred.until
    if "since" in filter.occurred.model_fields_set:
        since: datetime = filter.occurred.since
    else:
        since = earlier_by(moment=until, duration=retention)
    if filter.order == EventOrder.DESC:
        page = await _read_newest_first(
            session=session,
            filter=filter,
            since=since,
            page_size=page_size,
            offset=offset,
            window_event_counts=window_event_counts,
        )
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
