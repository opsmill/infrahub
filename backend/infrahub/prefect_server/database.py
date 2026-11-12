from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage import INTERACTIVE_PAGE_SIZE
from prefect.server.events.storage.database import raw_count_events, read_events

from .models import InfrahubDatabaseVersion

if TYPE_CHECKING:
    from prefect.server.events.filters import EventFilter
    from sqlalchemy.ext.asyncio import AsyncSession


async def query_events(
    session: AsyncSession, filter: EventFilter, page_size: int = INTERACTIVE_PAGE_SIZE, offset: int | None = None
) -> tuple[list[ReceivedEvent], int]:
    count = await raw_count_events(session, filter)  # type: ignore[attr-defined]
    page = await read_events(session, filter, limit=page_size, offset=offset)  # type: ignore[attr-defined]
    events = [ReceivedEvent.model_validate(e, from_attributes=True) for e in page]
    return events, count


async def read_database_version(session: AsyncSession) -> InfrahubDatabaseVersion:
    """Return the type and server version of the database the task manager stores its data in."""
    connection = await session.connection()
    version_info = connection.dialect.server_version_info
    return InfrahubDatabaseVersion(
        type=connection.dialect.name,
        version=".".join(str(part) for part in version_info) if version_info else None,
    )
