from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from prefect.server.database import provide_database_interface
from prefect.server.events.schemas.events import ReceivedEvent, RelatedResource, Resource
from prefect.server.events.storage.database import write_events

if TYPE_CHECKING:
    from datetime import datetime

    from infrahub.events.models import InfrahubEvent


async def seed_infrahub_event(event: InfrahubEvent, occurred: datetime) -> UUID:
    """Store an Infrahub event in the task manager's database as if it had occurred at the given time."""
    received = ReceivedEvent(
        id=event.meta.id,
        event=event.event_name,
        occurred=occurred,
        resource=Resource(event.get_resource()),
        related=[RelatedResource(item) for item in event.get_related()],
        payload=event.get_event_payload(),
    )
    await _store(events=[received])
    return received.id


async def seed_prefect_event(event_name: str, occurred: datetime) -> UUID:
    """Store a Prefect event about a flow run, with its flow as related item, as if it had occurred at the given time."""
    received = ReceivedEvent(
        id=uuid4(),
        event=event_name,
        occurred=occurred,
        resource=Resource({"prefect.resource.id": f"prefect.flow-run.{uuid4()}"}),
        related=[RelatedResource({"prefect.resource.id": f"prefect.flow.{uuid4()}", "prefect.resource.role": "flow"})],
    )
    await _store(events=[received])
    return received.id


async def _store(events: list[ReceivedEvent]) -> None:
    db = provide_database_interface()
    # Takes the SQLite write lock up front, so a concurrent writer makes the insert wait rather than fail as locked.
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        await write_events(session=session, events=events)
