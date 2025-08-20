from typing import Any

from prefect import task
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import WorkerStatus

from infrahub.events.utils import get_all_events
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType

from .models import TelemetryPrefectData, TelemetryWorkPoolData


@task(name="telemetry-gather-work-pools", task_run_name="Gather Work Pools", cache_policy=NONE)
async def gather_prefect_work_pools(client: PrefectClient) -> list[TelemetryWorkPoolData]:
    work_pools = await client.read_work_pools()
    data: list[TelemetryWorkPoolData] = []

    for pool in work_pools:
        workers = await client.read_workers_for_work_pool(work_pool_name=pool.name)
        data.append(
            TelemetryWorkPoolData(
                name=pool.name,
                type=pool.type,
                total_workers=len(workers),
                active_workers=len([item for item in workers if item.status == WorkerStatus.ONLINE]),
            )
        )

    return data


@task(name="telemetry-gather-events", task_run_name="Gather Events", cache_policy=NONE)
async def gather_prefect_events(client: PrefectClient) -> dict[str, Any]:
    infrahub_events = get_all_events()
    events: dict[str, int] = {}

    async def count_events(event_name: str) -> int:
        payload = {"filter": {"event": {"name": [event_name]}}}
        response = await client._client.post("/events/count-by/event", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or len(data) == 0:
            return 0
        return data[0]["count"]

    for event in infrahub_events:
        events[event.event_name] = await count_events(event_name=event.event_name)

    return events


@task(name="telemetry-gather-automations", task_run_name="Gather Automations", cache_policy=NONE)
async def gather_prefect_automations(client: PrefectClient) -> dict[str, Any]:
    automations = await client.read_automations()

    data: dict[str, Any] = {}

    for trigger_type in TriggerType:
        data[trigger_type.value] = len(
            [item for item in automations if item.name.startswith(f"{trigger_type.value}{NAME_SEPARATOR}")]
        )

    return data


@task(name="telemetry-gather-prefect-information", task_run_name="Gather Prefect Information", cache_policy=NONE)
async def gather_prefect_information() -> TelemetryPrefectData:
    async with get_client(sync_client=False) as client:
        data = TelemetryPrefectData(
            work_pools=await gather_prefect_work_pools(client=client),
            events=await gather_prefect_events(client=client),
            automations=await gather_prefect_automations(client=client),
        )

        return data
