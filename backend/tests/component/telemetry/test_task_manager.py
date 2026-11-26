import asyncio
import sqlite3
import uuid
from collections.abc import AsyncGenerator, Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import State, StateType
from prefect.events.schemas.events import Event, RelatedResource, Resource

from infrahub.events.account_action import AccountLoggedInEvent
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.branch_action import BranchCreatedEvent, BranchDeletedEvent, BranchMergedEvent
from infrahub.events.utils import get_all_events
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent, ValidatorStartedEvent
from infrahub.telemetry.models import TelemetryWorkflowRunData
from infrahub.telemetry.task_manager import (
    NODE_KIND_LABEL,
    count_started_validators,
    count_webhook_runs,
    count_windowed_event,
    count_windowed_unique_resources,
    gather_activity_24h,
    gather_prefect_events,
    gather_prefect_information,
    gather_task_manager_database,
    gather_workflow_runs,
)
from infrahub.telemetry.utils import floor_to_midnight_utc, get_activity_window
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_GENERATE, REQUEST_GENERATOR_RUN, WEBHOOK_PROCESS

if TYPE_CHECKING:
    from prefect.types import DateTime

LOGIN_EVENT_NAME = AccountLoggedInEvent.event_name
WEBHOOK_FLOW_NAME = WEBHOOK_PROCESS.name

# A day no other test seeds a run into, so the run rows are exact whatever else the shared task manager holds.
_RUN_DAY_START = datetime(2021, 3, 1, tzinfo=UTC)
_RUN_DAY_END = datetime(2021, 3, 2, tzinfo=UTC)

# The workflow names are read by name in the data warehouse, so the list is pinned here.
_REPORTED_WORKFLOW_NAMES = [
    "generator-run",
    "run-generator-as-check",
    "artifact-generate",
    "git-repository-check-artifact-create",
    "git-repository-run-user-check",
    "transform_render_python",
    "transform_render_jinja2_template",
    "proposed-changed-pipeline",
]


async def _post_events(client: PrefectClient, events: list[Event]) -> None:
    """Send events with explicit ``occurred`` timestamps and wait for the last to be queryable.

    Raises:
        Exception: If the last event is not queryable within the wait budget.

    """
    await client._client.post("/events", json=[event.model_dump(mode="json") for event in events])
    last_id = events[-1].id
    body = {"filter": {"id": {"id": [str(last_id)]}}}
    for _ in range(60):
        response = await client._client.post("/events/filter", json=body)
        response.raise_for_status()
        if response.json().get("events"):
            return
        await asyncio.sleep(1)
    raise Exception(f"Event {last_id} not found")


def _login_event(account_id: str, occurred: datetime) -> Event:
    return Event(
        id=uuid.uuid4(),
        event=LOGIN_EVENT_NAME,
        occurred=cast("DateTime", occurred),
        resource=Resource({"prefect.resource.id": f"infrahub.account.{account_id}"}),
    )


def _named_event(event_name: str, occurred: datetime, resource_id: str) -> Event:
    """Build a Prefect event of one name at an explicit instant.

    The windowed tally counts by event name over an ``occurred`` window, so only the name and
    timestamp drive the assertions; the resource id is unique-per-event to keep records distinct.
    """
    return Event(
        id=uuid.uuid4(),
        event=event_name,
        occurred=cast("DateTime", occurred),
        resource=Resource({"prefect.resource.id": resource_id}),
    )


class UnreadableKindsError(Exception):
    """Raised by the reader double that cannot read the validator kinds."""


def _kinds(*names: str) -> Callable[[], list[str]]:
    """Return a reader of validator kinds that gives the listed names."""

    def read_kinds() -> list[str]:
        return list(names)

    return read_kinds


def _unreadable_kinds() -> list[str]:
    raise UnreadableKindsError("The validator kinds cannot be read")


def _validator_started_event(kind: str, occurred: datetime, related_kind: str | None = None) -> Event:
    """Build a validator-started event whose own resource has the given kind.

    ``related_kind`` adds a related resource of another kind, as a validator event has for its proposed change.
    """
    related = []
    if related_kind is not None:
        related.append(
            RelatedResource(
                {
                    "prefect.resource.id": str(uuid.uuid4()),
                    "prefect.resource.role": "infrahub.related.node",
                    NODE_KIND_LABEL: related_kind,
                }
            )
        )
    return Event(
        id=uuid.uuid4(),
        event=ValidatorStartedEvent.event_name,
        occurred=cast("DateTime", occurred),
        resource=Resource({"prefect.resource.id": str(uuid.uuid4()), NODE_KIND_LABEL: kind}),
        related=related,
    )


async def _seed_run(
    client: PrefectClient,
    flow_id: uuid.UUID,
    expected_start: datetime,
    end_state: StateType | None,
    state_name: str | None = None,
) -> None:
    """Create a flow run expected to start at ``expected_start`` and move it to ``end_state``.

    ``None`` leaves the run in the running state.
    """
    response = await client._client.post(
        "/flow_runs/",
        json={
            "flow_id": str(flow_id),
            "state": {
                "type": StateType.SCHEDULED.value,
                "name": "Scheduled",
                "state_details": {"scheduled_time": expected_start.isoformat()},
            },
        },
    )
    response.raise_for_status()
    run_id = response.json()["id"]
    await client.set_flow_run_state(run_id, State(type=StateType.RUNNING, name="Running"), force=True)
    if end_state is not None:
        await client.set_flow_run_state(
            run_id, State(type=end_state, name=state_name or end_state.value.capitalize()), force=True
        )


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture(scope="module")
async def seeded_logins(prefect_client: PrefectClient) -> str:
    """Seed login events around the previous-UTC-day window; return the shared account suffix.

    The window the production code computes from "now" is the previous full UTC calendar day
    [window_start, window_end). Events are placed relative to that real boundary:
    - account ``a``: two logins inside the window (repeat → one unique bucket)
    - account ``b``: one login inside the window
    - account ``atstart``: one login at exactly window_start (included — half-open interval)
    - account ``atend``: one login at exactly window_end (excluded — belongs to the next day;
      counting it here as well would double-count it across two consecutive daily windows)
    - account ``before``: one login one minute before window_start (excluded)
    - account ``after``: one login one minute after window_end (excluded)

    Seeding relative to the real boundary (instead of a frozen clock) keeps the window the
    gather later computes identical to the one used here, and proves the count is anchored to
    midnight rather than to "now".
    """
    window_start, window_end = get_activity_window()
    suffix = uuid.uuid4().hex[:8]
    acct_a = f"a-{suffix}"
    acct_b = f"b-{suffix}"
    in_window = window_start + timedelta(hours=12)
    events = [
        _login_event(acct_a, in_window),
        _login_event(acct_a, in_window + timedelta(minutes=5)),
        _login_event(acct_b, in_window),
        _login_event(f"atstart-{suffix}", window_start),
        _login_event(f"atend-{suffix}", window_end),
        _login_event(f"before-{suffix}", window_start - timedelta(minutes=1)),
        _login_event(f"after-{suffix}", window_end + timedelta(minutes=1)),
    ]
    await _post_events(prefect_client, events)
    return suffix


# Each check/artifact/branch metric gets a distinct in-window count so a mis-wired field (one
# reading another's event name) would not coincidentally pass. Every event name also gets one
# event placed just before window_start to prove out-of-window records are excluded.
# The started validators per kind; their sum is the in-window count of the validator-started event below.
_STARTED_VALIDATOR_KIND_COUNTS: dict[str, int] = {"TestAlphaValidator": 2, "TestBetaValidator": 1}

_ACTIVITY_IN_WINDOW_COUNTS: dict[str, int] = {
    ValidatorStartedEvent.event_name: 3,
    ValidatorPassedEvent.event_name: 2,
    ValidatorFailedEvent.event_name: 1,
    ArtifactCreatedEvent.event_name: 2,
    ArtifactUpdatedEvent.event_name: 3,
    BranchCreatedEvent.event_name: 2,
    BranchMergedEvent.event_name: 1,
    BranchDeletedEvent.event_name: 3,
}


@pytest.fixture(scope="module")
async def seeded_activity(prefect_client: PrefectClient) -> dict[str, int]:
    """Seed validator/artifact/branch events around the previous-UTC-day window.

    For each event name, places its mapped number of events inside the window and exactly one a
    minute before window_start (which must be excluded). Returns the in-window count per event
    name so the assertions read the expected totals from the same source that seeded them.
    """
    window_start, _ = get_activity_window()
    suffix = uuid.uuid4().hex[:8]
    in_window = window_start + timedelta(hours=12)
    out_of_window = window_start - timedelta(minutes=1)
    events: list[Event] = []
    for event_name, count in _ACTIVITY_IN_WINDOW_COUNTS.items():
        if event_name == ValidatorStartedEvent.event_name:
            for kind, kind_count in _STARTED_VALIDATOR_KIND_COUNTS.items():
                events.extend(_validator_started_event(kind=kind, occurred=in_window) for _ in range(kind_count))
                events.append(_validator_started_event(kind=kind, occurred=out_of_window))
            continue
        for index in range(count):
            events.append(
                _named_event(event_name, in_window, f"{event_name}.{suffix}.in.{index}"),
            )
        events.append(_named_event(event_name, out_of_window, f"{event_name}.{suffix}.out"))
    await _post_events(prefect_client, events)
    return dict(_ACTIVITY_IN_WINDOW_COUNTS)


async def test_window_is_previous_full_utc_day() -> None:
    # Off-midnight "now" → window is the previous full UTC calendar day, anchored to midnight.
    now = datetime(2026, 6, 28, 2, 37, 0, tzinfo=UTC)
    window_start, window_end = get_activity_window(now=now)
    assert window_start == datetime(2026, 6, 27, 0, 0, 0, tzinfo=UTC)
    assert window_end == datetime(2026, 6, 28, 0, 0, 0, tzinfo=UTC)
    assert window_end - window_start == timedelta(hours=24)


async def test_floor_to_midnight_utc() -> None:
    floored = floor_to_midnight_utc(datetime(2026, 6, 28, 2, 37, 41, 123, tzinfo=UTC))
    assert floored == datetime(2026, 6, 28, 0, 0, 0, tzinfo=UTC)


async def test_windowed_logins_count(prefect_client: PrefectClient, seeded_logins: str) -> None:
    window_start, window_end = get_activity_window()
    count = await count_windowed_event.fn(
        client=prefect_client,
        event_name=LOGIN_EVENT_NAME,
        window_start=window_start,
        window_end=window_end,
    )
    # Four in-window logins (two from account a, one from account b, one at exactly
    # window_start). The event at exactly window_end and the before/after events are excluded —
    # proving the interval is half-open and anchored to midnight, not to now.
    assert count == 4


async def test_windowed_unique_logins_count(prefect_client: PrefectClient, seeded_logins: str) -> None:
    window_start, window_end = get_activity_window()
    unique = await count_windowed_unique_resources.fn(
        client=prefect_client,
        event_name=LOGIN_EVENT_NAME,
        window_start=window_start,
        window_end=window_end,
    )
    # Three distinct accounts in-window (a, b, atstart); account a's repeat login collapses.
    assert unique == 3


async def test_windowed_logins_exclude_out_of_window(prefect_client: PrefectClient, seeded_logins: str) -> None:
    # A window entirely in the past (well before any seeded event) must count nothing.
    past_start = datetime(2020, 1, 1, tzinfo=UTC)
    past_end = datetime(2020, 1, 2, tzinfo=UTC)
    count = await count_windowed_event.fn(
        client=prefect_client,
        event_name=LOGIN_EVENT_NAME,
        window_start=past_start,
        window_end=past_end,
    )
    assert count == 0


async def test_webhook_success_failure_split(prefect_client: PrefectClient) -> None:
    flow_id = await prefect_client.create_flow_from_name(WEBHOOK_FLOW_NAME)

    async def seed(terminal: StateType | None) -> None:
        response = await prefect_client._client.post("/flow_runs/", json={"flow_id": str(flow_id)})
        response.raise_for_status()
        run_id = response.json()["id"]
        await prefect_client.set_flow_run_state(run_id, State(type=StateType.RUNNING, name="Running"), force=True)
        if terminal is not None:
            await prefect_client.set_flow_run_state(
                run_id, State(type=terminal, name=terminal.value.capitalize()), force=True
            )

    # The ephemeral server stamps start_time at wall-clock time on the RUNNING transition
    # (a client-supplied state timestamp is rejected), so bracket the real seeding instant.
    before = datetime.now(tz=UTC) - timedelta(minutes=1)
    await seed(StateType.COMPLETED)
    await seed(StateType.COMPLETED)
    await seed(StateType.FAILED)
    await seed(StateType.CRASHED)
    await seed(None)  # non-terminal RUNNING — counted as neither
    after = datetime.now(tz=UTC) + timedelta(minutes=1)

    success, failure = await count_webhook_runs.fn(
        client=prefect_client,
        window_start=before,
        window_end=after,
    )
    assert success == 2
    assert failure == 2


async def test_webhook_split_excludes_out_of_window(prefect_client: PrefectClient) -> None:
    # No webhook-process run was stamped in this far-past window.
    past_start = datetime(2020, 1, 1, tzinfo=UTC)
    past_end = datetime(2020, 1, 2, tzinfo=UTC)
    success, failure = await count_webhook_runs.fn(
        client=prefect_client,
        window_start=past_start,
        window_end=past_end,
    )
    assert success == 0
    assert failure == 0


async def test_gather_activity_24h_logins(prefect_client: PrefectClient, seeded_logins: str) -> None:
    data = await gather_activity_24h.fn(client=prefect_client, read_validator_kinds=_kinds())
    # Login fields reflect exactly the in-window seeded events (incl. the one at exactly
    # window_start; the one at exactly window_end belongs to the next day).
    assert data.logins == 4
    assert data.unique_logins == 3
    # Webhook fields are present (an empty window is 0, not null). Webhook runs seeded by
    # other tests are stamped at "today", which is after the previous-day window the gather
    # computes, so this assertion does not depend on cross-test ordering for a 0.
    assert data.webhooks_fired_success is not None
    assert data.webhooks_fired_failure is not None


async def test_gather_activity_24h_checks_artifacts_branches(
    prefect_client: PrefectClient, seeded_activity: dict[str, int]
) -> None:
    # Each field equals exactly the in-window seeded count for its mapped event; the single
    # out-of-window event per name is excluded, so the count never inflates past the in-window
    # total. One gather covers every field: the flow computes them all in a single pass.
    data = await gather_activity_24h.fn(client=prefect_client, read_validator_kinds=_kinds())
    assert data.checks_started == seeded_activity[ValidatorStartedEvent.event_name]
    assert data.checks_passed == seeded_activity[ValidatorPassedEvent.event_name]
    assert data.checks_failed == seeded_activity[ValidatorFailedEvent.event_name]
    assert data.artifacts_created == seeded_activity[ArtifactCreatedEvent.event_name]
    assert data.artifacts_updated == seeded_activity[ArtifactUpdatedEvent.event_name]
    assert data.branches_created == seeded_activity[BranchCreatedEvent.event_name]
    assert data.branches_merged == seeded_activity[BranchMergedEvent.event_name]
    assert data.branches_deleted == seeded_activity[BranchDeletedEvent.event_name]


async def test_gather_activity_24h_validators_started_per_kind(
    prefect_client: PrefectClient, seeded_activity: dict[str, int]
) -> None:
    data = await gather_activity_24h.fn(
        client=prefect_client,
        read_validator_kinds=_kinds("TestAlphaValidator", "TestBetaValidator", "TestNeverStartedValidator"),
    )

    # The event of each kind seeded one minute before the window is left out, and a kind with no event is 0.
    assert data.validators_started == {"TestAlphaValidator": 2, "TestBetaValidator": 1, "TestNeverStartedValidator": 0}
    assert data.checks_started == 3


async def test_count_started_validators_reads_the_kind_of_the_validator_only(prefect_client: PrefectClient) -> None:
    # The day before the activity window, so these events do not change the counts the other tests assert.
    activity_start, _ = get_activity_window()
    window_start = activity_start - timedelta(hours=24)
    in_window = window_start + timedelta(hours=12)
    suffix = uuid.uuid4().hex[:8]
    kind = f"TestGammaValidator{suffix}"
    other_kind = f"TestDeltaValidator{suffix}"
    passed_event = Event(
        id=uuid.uuid4(),
        event=ValidatorPassedEvent.event_name,
        occurred=cast("DateTime", in_window),
        resource=Resource({"prefect.resource.id": str(uuid.uuid4()), NODE_KIND_LABEL: kind}),
    )
    await _post_events(
        prefect_client,
        [
            _validator_started_event(kind=kind, occurred=in_window),
            # A started validator of another kind whose related resource has the counted kind.
            _validator_started_event(kind=other_kind, occurred=in_window, related_kind=kind),
            passed_event,
        ],
    )

    counts = await count_started_validators(
        client=prefect_client,
        read_kinds=_kinds(kind, other_kind),
        window_start=window_start,
        window_end=activity_start,
    )

    assert counts == {kind: 1, other_kind: 1}


async def test_gather_activity_24h_unreadable_validator_kinds_nulls_only_the_count_per_kind(
    prefect_client: PrefectClient, seeded_activity: dict[str, int]
) -> None:
    data = await gather_activity_24h.fn(client=prefect_client, read_validator_kinds=_unreadable_kinds)

    assert data.validators_started is None
    assert data.checks_started == seeded_activity[ValidatorStartedEvent.event_name]
    assert data.branches_created == seeded_activity[BranchCreatedEvent.event_name]
    # No reported workflow ran in the activity window.
    assert data.workflow_runs == []


async def test_gather_workflow_runs_rows_per_workflow_and_end_state(prefect_client: PrefectClient) -> None:
    generator_flow = await prefect_client.create_flow_from_name(REQUEST_GENERATOR_RUN.name)
    artifact_flow = await prefect_client.create_flow_from_name(REQUEST_ARTIFACT_GENERATE.name)
    other_flow = await prefect_client.create_flow_from_name("a-workflow-that-is-not-reported")
    noon = _RUN_DAY_START + timedelta(hours=12)

    await _seed_run(prefect_client, generator_flow, noon, StateType.COMPLETED)
    await _seed_run(prefect_client, generator_flow, noon, StateType.COMPLETED)
    # Two state names of one state type are one row.
    await _seed_run(prefect_client, generator_flow, noon, StateType.FAILED)
    await _seed_run(prefect_client, generator_flow, noon, StateType.FAILED, state_name="TimedOut")
    await _seed_run(prefect_client, generator_flow, noon, StateType.CRASHED)
    # A run that has not ended is in no row.
    await _seed_run(prefect_client, generator_flow, noon, None)
    # The window includes its start and excludes its end.
    await _seed_run(prefect_client, generator_flow, _RUN_DAY_START, StateType.COMPLETED)
    await _seed_run(prefect_client, generator_flow, _RUN_DAY_END, StateType.COMPLETED)
    await _seed_run(prefect_client, generator_flow, _RUN_DAY_START - timedelta(minutes=1), StateType.COMPLETED)
    await _seed_run(prefect_client, artifact_flow, noon, StateType.CANCELLED)
    await _seed_run(prefect_client, other_flow, noon, StateType.COMPLETED)

    rows = await gather_workflow_runs(client=prefect_client, window_start=_RUN_DAY_START, window_end=_RUN_DAY_END)

    assert [(row.workflow, row.state, row.runs) for row in rows] == [
        ("generator-run", "COMPLETED", 3),
        ("generator-run", "FAILED", 2),
        ("generator-run", "CRASHED", 1),
        ("artifact-generate", "CANCELLED", 1),
    ]
    # The run time is a whole number; its value depends on how long the seeding took.
    assert [type(row.run_seconds) for row in rows] == [int, int, int, int]


async def test_gather_workflow_runs_reports_each_failed_read(prefect_client: PrefectClient) -> None:
    # The task manager rejects a window that ends before it starts, so every read fails.
    rows = await gather_workflow_runs(client=prefect_client, window_start=_RUN_DAY_END, window_end=_RUN_DAY_START)

    assert rows == [TelemetryWorkflowRunData(workflow=name) for name in _REPORTED_WORKFLOW_NAMES]


async def test_gather_prefect_events_unchanged(prefect_client: PrefectClient, seeded_logins: str) -> None:
    """The existing unwindowed tally still returns a count for every Infrahub event name."""
    events = await gather_prefect_events.fn(client=prefect_client)
    expected_names = {event.event_name for event in get_all_events()}
    assert set(events.keys()) == expected_names
    # The unwindowed login tally includes the out-of-window boundary events too, so it is
    # at least the five seeded logins — i.e. it is NOT the windowed count of 3.
    assert events[LOGIN_EVENT_NAME] >= 5


async def test_gather_prefect_information(prefect_test_fixture: Generator) -> None:
    data = await gather_prefect_information()
    assert data


async def test_gather_task_manager_database(prefect_client: PrefectClient) -> None:
    data = await gather_task_manager_database.fn(client=prefect_client)
    # The test task manager runs on this interpreter and stores its data in SQLite.
    assert data.type == "sqlite"
    assert data.version == sqlite3.sqlite_version
