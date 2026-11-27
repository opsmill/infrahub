import asyncio
from collections.abc import Awaitable, Callable
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
from pydantic import BaseModel, TypeAdapter

from infrahub.events.account_action import AccountLoggedInEvent
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.branch_action import BranchCreatedEvent, BranchDeletedEvent, BranchMergedEvent
from infrahub.events.utils import get_all_events
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent, ValidatorStartedEvent
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    GIT_REPOSITORY_USER_CHECK_RUN,
    REQUEST_ARTIFACT_GENERATE,
    REQUEST_GENERATOR_RUN,
    REQUEST_PROPOSED_CHANGE_PIPELINE,
    RUN_GENERATOR_AS_CHECK,
    TRANSFORM_JINJA2_RENDER,
    TRANSFORM_PYTHON_RENDER,
    WEBHOOK_PROCESS,
)

from .constants import WorkflowRunState
from .models import (
    TelemetryActivity24hData,
    TelemetryPrefectData,
    TelemetryTaskManagerDatabaseData,
    TelemetryWorkflowRunData,
    TelemetryWorkPoolData,
)
from .utils import get_activity_window, inclusive_end, safe_metric

WEBHOOK_FLOW_NAME = WEBHOOK_PROCESS.name
WEBHOOK_FAILURE_STATES = [StateType.FAILED, StateType.CRASHED]
DATABASE_VERSION_PATH = "/infrahub/database/version"
RUN_HISTORY_PATH = "/flow_runs/history"
NODE_KIND_LABEL = "infrahub.node.kind"
REPORTED_WORKFLOW_NAMES = [
    REQUEST_GENERATOR_RUN.name,
    RUN_GENERATOR_AS_CHECK.name,
    REQUEST_ARTIFACT_GENERATE.name,
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
    GIT_REPOSITORY_USER_CHECK_RUN.name,
    TRANSFORM_PYTHON_RENDER.name,
    TRANSFORM_JINJA2_RENDER.name,
    REQUEST_PROPOSED_CHANGE_PIPELINE.name,
]
REPORTED_RUN_STATES = {
    StateType.COMPLETED: WorkflowRunState.COMPLETED,
    StateType.FAILED: WorkflowRunState.FAILED,
    StateType.CRASHED: WorkflowRunState.CRASHED,
    StateType.CANCELLED: WorkflowRunState.CANCELLED,
}

# One request timeout of the task manager client by default, so a read that gets no answer is not tried again.
TASK_MANAGER_READ_DEADLINE_SECONDS = 60.0

type ValidatorKindReader = Callable[[], list[str]]


class RunHistoryState(BaseModel):
    """The runs in one state within one interval of the run history."""

    state_type: StateType
    count_runs: int
    sum_estimated_run_time: timedelta


class RunHistoryInterval(BaseModel):
    states: list[RunHistoryState]


_RUN_HISTORY_ADAPTER = TypeAdapter(list[RunHistoryInterval])


class EventCountBucket(BaseModel):
    """One bucket of a count-by response of the task manager."""

    count: int


_EVENT_COUNT_ADAPTER = TypeAdapter(list[EventCountBucket])


async def read_within_deadline[T](read: Awaitable[T], deadline_seconds: float) -> T:
    """Await a read of the task manager and stop waiting when the deadline passes.

    Raises:
        TimeoutError: If the read has not returned after ``deadline_seconds``.

    """
    deadline = asyncio.timeout(deadline_seconds)
    try:
        async with deadline:
            return await read
    except TimeoutError as exc:
        if not deadline.expired():
            raise
        raise TimeoutError(f"The task manager did not answer within {deadline_seconds} seconds") from exc


async def _post_count_by(client: PrefectClient, path: str, payload: dict[str, Any]) -> Any:
    """POST a Prefect count-by query and return the decoded response."""
    response = await client._client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


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

    for event in infrahub_events:
        payload = {"filter": {"event": {"name": [event.event_name]}}}
        response = await _post_count_by(client=client, path="/events/count-by/event", payload=payload)
        # This tally has no null value, so a response that is not a list of buckets counts as no event.
        buckets = response if isinstance(response, list) else []
        events[event.event_name] = sum(bucket.get("count", 0) for bucket in buckets)

    return events


def _windowed_event_filter(
    event_name: str,
    window_start: datetime,
    window_end: datetime,
    resource_labels: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Build the count-by filter for the half-open window ``[window_start, window_end)``.

    ``resource_labels`` keeps only the events whose own resource has one of the listed values for each label.
    """
    event_filter: dict[str, Any] = {
        "event": {"name": [event_name]},
        "occurred": {"since": window_start.isoformat(), "until": inclusive_end(window_end).isoformat()},
    }
    if resource_labels:
        event_filter["resource"] = {"labels": resource_labels}
    return {"filter": event_filter}


@task(name="telemetry-gather-windowed-event", task_run_name="Gather Windowed Event Count", cache_policy=NONE)
async def count_windowed_event(
    client: PrefectClient,
    event_name: str,
    window_start: datetime,
    window_end: datetime,
    resource_labels: dict[str, list[str]] | None = None,
) -> int:
    """Count events of one name that occurred within ``[window_start, window_end)``.

    Raises:
        pydantic.ValidationError: If the response is not a list of buckets that each have a count.

    """
    payload = _windowed_event_filter(
        event_name=event_name, window_start=window_start, window_end=window_end, resource_labels=resource_labels
    )
    response = await _post_count_by(client=client, path="/events/count-by/event", payload=payload)
    return sum(bucket.count for bucket in _EVENT_COUNT_ADAPTER.validate_python(response))


@task(name="telemetry-gather-windowed-unique", task_run_name="Gather Windowed Unique Count", cache_policy=NONE)
async def count_windowed_unique_resources(
    client: PrefectClient, event_name: str, window_start: datetime, window_end: datetime
) -> int:
    """Count distinct resources emitting one event within ``[window_start, window_end)``.

    Raises:
        pydantic.ValidationError: If the response is not a list of buckets that each have a count.

    """
    payload = _windowed_event_filter(event_name=event_name, window_start=window_start, window_end=window_end)
    response = await _post_count_by(client=client, path="/events/count-by/resource", payload=payload)
    return len(_EVENT_COUNT_ADAPTER.validate_python(response))


@task(name="telemetry-gather-webhook-runs", task_run_name="Gather Webhook Runs", cache_policy=NONE)
async def count_webhook_runs(client: PrefectClient, window_start: datetime, window_end: datetime) -> tuple[int, int]:
    """Return ``(success, failure)`` webhook flow-run counts started within the window.

    Success = terminal ``COMPLETED``; failure = terminal ``FAILED``/``CRASHED``; non-terminal
    runs count in neither.
    """
    flow_filter = FlowFilter(name=FlowFilterName(any_=[WEBHOOK_FLOW_NAME]))
    after = DateTime.fromisoformat(window_start.isoformat())
    before = DateTime.fromisoformat(inclusive_end(window_end).isoformat())

    def runs_in_states(states: list[StateType]) -> FlowRunFilter:
        return FlowRunFilter(
            start_time=FlowRunFilterStartTime(after_=after, before_=before),
            state=FlowRunFilterState(type=FlowRunFilterStateType(any_=states)),
        )

    # count_flow_runs returns a server-side count. read_flow_runs is deliberately not used here:
    # it pages at the API limit and would undercount a busy day.
    success = await client.count_flow_runs(
        flow_filter=flow_filter, flow_run_filter=runs_in_states([StateType.COMPLETED])
    )
    failure = await client.count_flow_runs(
        flow_filter=flow_filter, flow_run_filter=runs_in_states(WEBHOOK_FAILURE_STATES)
    )
    return success, failure


async def count_started_validators(
    client: PrefectClient,
    read_kinds: ValidatorKindReader,
    window_start: datetime,
    window_end: datetime,
    read_deadline_seconds: float,
) -> dict[str, int | None]:
    """Count the validators of each kind that started within ``[window_start, window_end)``.

    ``read_kinds`` is called before any count, and an error it raises is not caught here. A kind whose
    count fails, or is not answered within ``read_deadline_seconds``, is reported as ``None`` and the
    other kinds keep their count.
    """
    counts: dict[str, int | None] = {}
    for kind in read_kinds():
        counts[kind] = await safe_metric(
            read_within_deadline(
                count_windowed_event.fn(
                    client=client,
                    event_name=ValidatorStartedEvent.event_name,
                    window_start=window_start,
                    window_end=window_end,
                    resource_labels={NODE_KIND_LABEL: [kind]},
                ),
                deadline_seconds=read_deadline_seconds,
            ),
            metric=f"activity_24h.validators_started.{kind}",
        )
    return counts


def build_workflow_run_rows(workflow: str, states: list[RunHistoryState]) -> list[TelemetryWorkflowRunData]:
    """Add up the history states of one workflow into one row per reported end state.

    The task manager returns one entry per state name, so several entries can share a state type.
    """
    runs: dict[StateType, int] = {}
    run_time: dict[StateType, timedelta] = {}
    for entry in states:
        runs[entry.state_type] = runs.get(entry.state_type, 0) + entry.count_runs
        run_time[entry.state_type] = run_time.get(entry.state_type, timedelta()) + entry.sum_estimated_run_time
    return [
        TelemetryWorkflowRunData(
            workflow=workflow,
            state=reported_state,
            runs=runs[state_type],
            run_seconds=round(run_time[state_type].total_seconds()),
        )
        for state_type, reported_state in REPORTED_RUN_STATES.items()
        if state_type in runs
    ]


async def read_workflow_run_history(
    client: PrefectClient, workflow: str, window_start: datetime, window_end: datetime
) -> list[TelemetryWorkflowRunData]:
    """Return the run rows of one workflow for the runs expected to start within ``[window_start, window_end)``.

    Raises:
        httpx.HTTPStatusError: If the task manager answers with an error status.
        httpx.TransportError: If the task manager cannot be reached or does not answer in time.
        json.JSONDecodeError: If the response is not JSON.
        pydantic.ValidationError: If the response does not contain the run count and run time per state.

    """
    payload = {
        "history_start": window_start.isoformat(),
        "history_end": window_end.isoformat(),
        "history_interval_seconds": (window_end - window_start).total_seconds(),
        "flows": {"name": {"any_": [workflow]}},
    }
    response = await client._client.post(RUN_HISTORY_PATH, json=payload)
    response.raise_for_status()
    intervals = _RUN_HISTORY_ADAPTER.validate_python(response.json())
    states = [state for interval in intervals for state in interval.states]
    return build_workflow_run_rows(workflow=workflow, states=states)


async def gather_workflow_runs(
    client: PrefectClient, window_start: datetime, window_end: datetime, read_deadline_seconds: float
) -> list[TelemetryWorkflowRunData]:
    """Return the run rows of every reported workflow for ``[window_start, window_end)``.

    A workflow whose history cannot be read, or is not answered within ``read_deadline_seconds``, gets one
    row with a null state and null counts, and the other workflows keep their rows.
    """
    rows: list[TelemetryWorkflowRunData] = []
    for workflow in REPORTED_WORKFLOW_NAMES:
        workflow_rows = await safe_metric(
            read_within_deadline(
                read_workflow_run_history(
                    client=client, workflow=workflow, window_start=window_start, window_end=window_end
                ),
                deadline_seconds=read_deadline_seconds,
            ),
            metric=f"activity_24h.workflow_runs.{workflow}",
        )
        if workflow_rows is None:
            rows.append(TelemetryWorkflowRunData(workflow=workflow))
        else:
            rows.extend(workflow_rows)
    return rows


@task(name="telemetry-gather-activity-24h", task_run_name="Gather 24h Activity", cache_policy=NONE)
async def gather_activity_24h(
    client: PrefectClient, read_validator_kinds: ValidatorKindReader
) -> TelemetryActivity24hData:
    """Assemble the 24h activity metrics over the previous full UTC calendar day.

    ``read_validator_kinds`` returns the validator kinds to count; when it raises, only the count per kind is ``None``.
    """
    window_start, window_end = get_activity_window()

    async def windowed_count(event_name: str) -> int | None:
        return await safe_metric(
            count_windowed_event.fn(
                client=client,
                event_name=event_name,
                window_start=window_start,
                window_end=window_end,
            ),
            metric=f"activity_24h count of the event {event_name}",
        )

    logins = await windowed_count(AccountLoggedInEvent.event_name)
    unique_logins = await safe_metric(
        count_windowed_unique_resources.fn(
            client=client,
            event_name=AccountLoggedInEvent.event_name,
            window_start=window_start,
            window_end=window_end,
        ),
        metric="activity_24h.unique_logins",
    )
    webhook_counts = await safe_metric(
        count_webhook_runs.fn(client=client, window_start=window_start, window_end=window_end),
        metric="activity_24h.webhooks_fired_success and webhooks_fired_failure",
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
        validators_started=await safe_metric(
            count_started_validators(
                client=client,
                read_kinds=read_validator_kinds,
                window_start=window_start,
                window_end=window_end,
                read_deadline_seconds=TASK_MANAGER_READ_DEADLINE_SECONDS,
            ),
            metric="activity_24h.validators_started",
        ),
        workflow_runs=await gather_workflow_runs(
            client=client,
            window_start=window_start,
            window_end=window_end,
            read_deadline_seconds=TASK_MANAGER_READ_DEADLINE_SECONDS,
        ),
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


@task(name="telemetry-gather-task-manager-database", task_run_name="Gather Task Manager Database", cache_policy=NONE)
async def gather_task_manager_database(client: PrefectClient) -> TelemetryTaskManagerDatabaseData:
    """Return the type and version of the database the task manager stores its data in.

    Raises:
        httpx.HTTPStatusError: If the task manager answers with an error status, for example 404 when it does not serve the route.
        pydantic.ValidationError: If the response does not contain the database type and version.

    """
    response = await client._client.get(DATABASE_VERSION_PATH)
    response.raise_for_status()
    return TelemetryTaskManagerDatabaseData.model_validate(response.json())


@task(name="telemetry-gather-prefect-information", task_run_name="Gather Prefect Information", cache_policy=NONE)
async def gather_prefect_information() -> TelemetryPrefectData:
    async with get_client(sync_client=False) as client:
        return TelemetryPrefectData(
            work_pools=await gather_prefect_work_pools(client=client),
            events=await gather_prefect_events(client=client),
            automations=await gather_prefect_automations(client=client),
        )
