import asyncio
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.events.filters import EventFilter, EventIDFilter, EventNameFilter
from prefect.events.schemas.events import Event, RelatedResource, Resource
from pydantic import TypeAdapter

from infrahub.events.models import InfrahubEvent


async def send_events(client: PrefectClient, events: list[InfrahubEvent]) -> list[Event]:
    events_data = [
        Event(
            id=event.meta.id,
            event=event.event_name,
            payload=event.get_event_payload(),
            related=[RelatedResource(item) for item in event.get_related()],
            resource=Resource(event.get_resource()),
        )
        for event in events
    ]
    await client._client.post("/events", json=[event.model_dump(mode="json") for event in events_data])

    # Ensure the events are available in the API, not sure why but we have to wait for them to be available
    last_event_id = events_data[-1].id
    for _ in range(10):
        if await has_event(client=client, event_id=last_event_id):
            return events_data
        await asyncio.sleep(1)
    raise Exception(f"Event {last_event_id} not found")


async def has_event(client: PrefectClient, event_id: UUID) -> bool:
    try:
        await query_event(client=client, event_id=event_id)
        return True
    except Exception:
        return False


async def query_event(client: PrefectClient, event_id: UUID) -> Event:
    filters = EventFilter(id=EventIDFilter(id=[event_id]))  # type: ignore[call-arg]
    body = {"filter": filters.model_dump(mode="json", exclude_unset=True)}

    response = await client._client.post("/events/filter", json=body)
    response.raise_for_status()
    events = TypeAdapter(list[Event]).validate_python(response.json().get("events"))

    if events and len(events) == 1:
        return events[0]

    raise Exception(f"No event found for id {event_id}")


async def query_events_by_name(client: PrefectClient, event_name: str) -> list[Event]:
    filters = EventFilter(event=EventNameFilter(name=[event_name]))  # type: ignore[call-arg]
    body = {"filter": filters.model_dump(mode="json", exclude_unset=True)}

    response = await client._client.post("/events/filter", json=body)
    response.raise_for_status()
    return TypeAdapter(list[Event]).validate_python(response.json().get("events"))


def extract_expected_ids(data: dict[str, InfrahubEvent], expected_events: list[str]) -> list[str]:
    return sorted([event.get_id() for name, event in data.items() if name in expected_events])
