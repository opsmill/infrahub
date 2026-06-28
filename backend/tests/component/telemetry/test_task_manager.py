import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import State, StateType
from prefect.events.schemas.events import Event, Resource

from infrahub.events.utils import get_all_events
from infrahub.telemetry.task_manager import (
    count_webhook_runs,
    count_windowed_event,
    count_windowed_unique_resources,
    gather_activity_24h,
    gather_prefect_events,
    gather_prefect_information,
)
from infrahub.telemetry.window import floor_to_midnight_utc, get_activity_window

LOGIN_EVENT_NAME = "infrahub.account.logged_in"
WEBHOOK_FLOW_NAME = "webhook-process"


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
        occurred=occurred,
        resource=Resource({"prefect.resource.id": f"infrahub.account.{account_id}"}),
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
        _login_event(f"before-{suffix}", window_start - timedelta(minutes=1)),
        _login_event(f"after-{suffix}", window_end + timedelta(minutes=1)),
    ]
    await _post_events(prefect_client, events)
    return suffix


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
    # Three in-window logins (two from account a, one from account b); the before/after
    # boundary events are excluded — proving the window is anchored to midnight, not now.
    assert count == 3


async def test_windowed_unique_logins_count(prefect_client: PrefectClient, seeded_logins: str) -> None:
    window_start, window_end = get_activity_window()
    unique = await count_windowed_unique_resources.fn(
        client=prefect_client,
        event_name=LOGIN_EVENT_NAME,
        window_start=window_start,
        window_end=window_end,
    )
    # Two distinct accounts in-window (a, b); account a's repeat login collapses.
    assert unique == 2


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
    data = await gather_activity_24h.fn(client=prefect_client)
    # Login fields reflect exactly the in-window seeded events.
    assert data.logins == 3
    assert data.unique_logins == 2
    # Webhook fields are present (an empty window is 0, not null). Webhook runs seeded by
    # other tests are stamped at "today", which is after the previous-day window the gather
    # computes, so this assertion does not depend on cross-test ordering for a 0.
    assert data.webhooks_fired_success is not None
    assert data.webhooks_fired_failure is not None
    # Fields owned by a later chunk stay null in this one.
    assert data.checks_started is None
    assert data.checks_passed is None
    assert data.checks_failed is None
    assert data.artifacts_created is None
    assert data.artifacts_updated is None
    assert data.branches_created is None
    assert data.branches_merged is None
    assert data.branches_deleted is None


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
