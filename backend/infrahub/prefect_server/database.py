from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from prefect.server.events.filters import EventOccurredFilter, EventOrder
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage import INTERACTIVE_PAGE_SIZE
from prefect.server.events.storage.database import raw_count_events, read_events

if TYPE_CHECKING:
    from collections.abc import Sequence

    from prefect.server.database.orm_models import ORMEvent
    from prefect.server.events.filters import EventFilter
    from sqlalchemy.ext.asyncio import AsyncSession

NEWEST_FIRST_WINDOWS = (timedelta(hours=1), timedelta(days=1), timedelta(days=7), timedelta(days=30))


def _between(filter: EventFilter, since: datetime, until: datetime) -> EventFilter:
    return filter.model_copy(update={"occurred": EventOccurredFilter(since=since, until=until)})


def earlier_by(moment: datetime, duration: timedelta) -> datetime:
    """Return the UTC time `duration` before `moment`, or the earliest UTC time a datetime holds when that is earlier."""
    earliest = datetime.min.replace(tzinfo=UTC)
    if moment - earliest <= duration:
        return earliest
    return moment.astimezone(UTC) - duration


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
        window_start = earlier_by(moment=until, duration=window)
        if window_start <= since:
            break
        page = await _read_page(session=session, filter=filter, since=window_start, page_size=page_size, offset=offset)
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
    if "since" in filter.occurred.model_fields_set:
        since: datetime = filter.occurred.since
    else:
        since = earlier_by(moment=until, duration=retention)
    if filter.order == EventOrder.DESC:
        page = await _read_newest_first(session=session, filter=filter, since=since, page_size=page_size, offset=offset)
    else:
        page = await _read_page(session=session, filter=filter, since=since, page_size=page_size, offset=offset)
    count = None
    if include_total:
        count = await raw_count_events(session, _between(filter=filter, since=since, until=until))  # type: ignore[attr-defined]
    events = [ReceivedEvent.model_validate(event, from_attributes=True) for event in page]
    return events, count
