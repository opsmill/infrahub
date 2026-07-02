from datetime import datetime, timedelta
from typing import Any

from prefect import task
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.filters import (
    FlowFilter,
    FlowFilterName,
    FlowRunFilter,
    FlowRunFilterStartTime,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType, WorkerStatus
from prefect.types import DateTime

from infrahub.events.account_action import AccountLoggedInEvent
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.branch_action import BranchCreatedEvent, BranchDeletedEvent, BranchMergedEvent
from infrahub.events.utils import get_all_events
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent, ValidatorStartedEvent
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations

from .models import TelemetryActivity24hData, TelemetryPrefectData, TelemetryWorkPoolData
from .utils import safe_metric
from .window import get_activity_window

WEBHOOK_FLOW_NAME = "webhook-process"
WEBHOOK_FAILURE_STATES = [StateType.FAILED, StateType.CRASHED]


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


def _windowed_event_filter(event_name: str, window_start: datetime, window_end: datetime) -> dict[str, Any]:
    """Build the count-by request body: an event-name filter narrowed to ``[start, end)``.

    Prefect's ``EventOccurredFilter`` treats both ``since`` and ``until`` as inclusive
    (``since <= occurred <= until``). The window contract is half-open, so ``until`` is pulled
    back by one microsecond — otherwise an event stamped exactly on the boundary would be
    counted in two consecutive windows.
    """
    until = window_end - timedelta(microseconds=1)
    return {
        "filter": {
            "event": {"name": [event_name]},
            "occurred": {"since": window_start.isoformat(), "until": until.isoformat()},
        }
    }


@task(name="telemetry-gather-windowed-event", task_run_name="Gather Windowed Event Count", cache_policy=NONE)
async def count_windowed_event(
    client: PrefectClient, event_name: str, window_start: datetime, window_end: datetime
) -> int:
    """Count events of one name that occurred within ``[window_start, window_end)``."""
    payload = _windowed_event_filter(event_name=event_name, window_start=window_start, window_end=window_end)
    response = await client._client.post("/events/count-by/event", json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        return 0
    return sum(bucket["count"] for bucket in data)


@task(name="telemetry-gather-windowed-unique", task_run_name="Gather Windowed Unique Count", cache_policy=NONE)
async def count_windowed_unique_resources(
    client: PrefectClient, event_name: str, window_start: datetime, window_end: datetime
) -> int:
    """Count distinct resources emitting one event name within ``[window_start, window_end)``.

    Counting by resource returns one bucket per distinct ``prefect.resource.id``, so the number
    of buckets is the distinct-resource total over the window.
    """
    payload = _windowed_event_filter(event_name=event_name, window_start=window_start, window_end=window_end)
    response = await client._client.post("/events/count-by/resource", json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        return 0
    return len(data)


@task(name="telemetry-gather-webhook-runs", task_run_name="Gather Webhook Runs", cache_policy=NONE)
async def count_webhook_runs(client: PrefectClient, window_start: datetime, window_end: datetime) -> tuple[int, int]:
    """Return ``(success, failure)`` webhook flow-run counts started within the window.

    Success is the count of runs in a terminal ``COMPLETED`` state; failure is the count in a
    terminal ``FAILED``/``CRASHED`` state. Runs still in a non-terminal state at gather time are
    counted in neither.
    """
    flow_filter = FlowFilter(name=FlowFilterName(any_=[WEBHOOK_FLOW_NAME]))
    # The flow-run start-time filter is typed with Prefect's own datetime; coerce the stdlib
    # boundaries to it so the comparison stays well-typed. ``before_`` is inclusive ("at or
    # before"), so pull it back one microsecond to keep the window half-open — a run starting
    # exactly on the boundary must land in exactly one window.
    after = DateTime.fromisoformat(window_start.isoformat())
    before = DateTime.fromisoformat((window_end - timedelta(microseconds=1)).isoformat())

    def runs_in_states(states: list[StateType]) -> FlowRunFilter:
        return FlowRunFilter(
            start_time=FlowRunFilterStartTime(after_=after, before_=before),
            state=FlowRunFilterState(type=FlowRunFilterStateType(any_=states)),
        )

    # Count server-side rather than reading run objects: read_flow_runs caps at the server
    # default page size (PREFECT_API_DEFAULT_LIMIT), which would silently undercount a busy
    # deployment's daily webhook volume. count_flow_runs returns an exact, unpaginated total.
    success = await client.count_flow_runs(
        flow_filter=flow_filter, flow_run_filter=runs_in_states([StateType.COMPLETED])
    )
    failure = await client.count_flow_runs(
        flow_filter=flow_filter, flow_run_filter=runs_in_states(WEBHOOK_FAILURE_STATES)
    )
    return success, failure


@task(name="telemetry-gather-activity-24h", task_run_name="Gather 24h Activity", cache_policy=NONE)
async def gather_activity_24h(client: PrefectClient) -> TelemetryActivity24hData:
    """Assemble the 24h activity metrics over the previous full UTC calendar day.

    Each source is isolated so one failing source nulls only its own field.
    """
    window_start, window_end = get_activity_window()

    async def windowed_count(event_name: str) -> int | None:
        return await safe_metric(
            count_windowed_event.fn(
                client=client,
                event_name=event_name,
                window_start=window_start,
                window_end=window_end,
            )
        )

    logins = await windowed_count(AccountLoggedInEvent.event_name)
    unique_logins = await safe_metric(
        count_windowed_unique_resources.fn(
            client=client,
            event_name=AccountLoggedInEvent.event_name,
            window_start=window_start,
            window_end=window_end,
        )
    )
    webhook_counts = await safe_metric(
        count_webhook_runs.fn(client=client, window_start=window_start, window_end=window_end)
    )
    webhooks_fired_success = webhook_counts[0] if webhook_counts is not None else None
    webhooks_fired_failure = webhook_counts[1] if webhook_counts is not None else None

    return TelemetryActivity24hData(
        logins=logins,
        unique_logins=unique_logins,
        checks_started=await windowed_count(ValidatorStartedEvent.event_name),
        checks_passed=await windowed_count(ValidatorPassedEvent.event_name),
        checks_failed=await windowed_count(ValidatorFailedEvent.event_name),
        artifacts_created=await windowed_count(ArtifactCreatedEvent.event_name),
        artifacts_updated=await windowed_count(ArtifactUpdatedEvent.event_name),
        branches_created=await windowed_count(BranchCreatedEvent.event_name),
        branches_merged=await windowed_count(BranchMergedEvent.event_name),
        branches_deleted=await windowed_count(BranchDeletedEvent.event_name),
        webhooks_fired_success=webhooks_fired_success,
        webhooks_fired_failure=webhooks_fired_failure,
    )


@task(name="telemetry-gather-automations", task_run_name="Gather Automations", cache_policy=NONE)
async def gather_prefect_automations(client: PrefectClient) -> dict[str, Any]:
    automations = await gather_all_automations(client=client)

    data: dict[str, Any] = {}

    for trigger_type in TriggerType:
        data[trigger_type.value] = len(
            [item for item in automations if item.name.startswith(f"{trigger_type.value}{NAME_SEPARATOR}")]
        )

    return data


@task(name="telemetry-gather-prefect-information", task_run_name="Gather Prefect Information", cache_policy=NONE)
async def gather_prefect_information() -> TelemetryPrefectData:
    async with get_client(sync_client=False) as client:
        return TelemetryPrefectData(
            work_pools=await gather_prefect_work_pools(client=client),
            events=await gather_prefect_events(client=client),
            automations=await gather_prefect_automations(client=client),
        )
