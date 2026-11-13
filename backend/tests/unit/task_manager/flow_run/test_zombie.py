from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import pytest
from prefect import State
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import FlowRun, FlowRunPolicy, StateDetails, StateType
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.task_manager.flow_run.zombie import (
    FLOW_RUNS_PAGE_SIZE,
    ZOMBIE_HEARTBEAT_WINDOW,
    ZombieFlowRunReaper,
    heartbeat_window,
)

# pendulum, Prefect's DateTime before Python 3.13, drops a standard-library tzinfo on arithmetic, and fromtimestamp
# converts the zone to pendulum's own UTC.
NOW = DateTime.fromtimestamp(datetime(2026, 11, 7, 12, 0, tzinfo=UTC).timestamp(), tz=UTC)
LONG_AGO = NOW - ZOMBIE_HEARTBEAT_WINDOW - timedelta(minutes=10)
RECENTLY = NOW - ZOMBIE_HEARTBEAT_WINDOW / 2


def make_running_run(running_since: DateTime) -> FlowRun:
    return FlowRun(
        flow_id=uuid4(),
        name="run",
        start_time=running_since,
        state=State(type=StateType.RUNNING, timestamp=running_since),
    )


def make_retry_wait(retry_due: DateTime, retry_type: Literal["in_process", "reschedule"] = "in_process") -> FlowRun:
    return FlowRun(
        flow_id=uuid4(),
        name="run",
        start_time=LONG_AGO,
        next_scheduled_start_time=retry_due,
        empirical_policy=FlowRunPolicy(retry_type=retry_type),
        state=State(
            type=StateType.SCHEDULED, name="AwaitingRetry", state_details=StateDetails(scheduled_time=retry_due)
        ),
    )


class InMemoryZombieClient:
    """Stores flow runs and heartbeat times, and filters them the way the task manager does."""

    def __init__(
        self,
        flow_runs: list[FlowRun],
        heartbeats: dict[UUID, list[DateTime]] | None = None,
        latest_event: DateTime | None = NOW,
        finished_meanwhile: set[UUID] | None = None,
    ) -> None:
        self.flow_runs = flow_runs
        self.heartbeats = heartbeats or {}
        self.latest_event = latest_event
        self.finished_meanwhile = finished_meanwhile or set()
        self.state_changes: list[tuple[UUID, State, bool]] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        assert flow_run_filter is not None
        assert flow_run_filter.state is not None
        assert flow_run_filter.state.type is not None
        types = flow_run_filter.state.type.any_ or []
        names = flow_run_filter.state.name.any_ if flow_run_filter.state.name is not None else None
        started_before = flow_run_filter.start_time.before_ if flow_run_filter.start_time is not None else None
        scheduled_before = (
            flow_run_filter.next_scheduled_start_time.before_
            if flow_run_filter.next_scheduled_start_time is not None
            else None
        )
        matching = [
            run
            for run in self.flow_runs
            if run.state is not None
            and run.state.type in types
            and (names is None or run.state.name in names)
            and (started_before is None or (run.start_time is not None and run.start_time <= started_before))
            and (
                scheduled_before is None
                or (run.next_scheduled_start_time is not None and run.next_scheduled_start_time <= scheduled_before)
            )
        ]
        end = None if limit is None else offset + limit
        return matching[offset:end]

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        raise NotImplementedError

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> StateType | None:
        self.state_changes.append((flow_run_id, state, force))
        if flow_run_id in self.finished_meanwhile:
            return StateType.COMPLETED
        return state.type

    async def latest_heartbeats(self, flow_run_ids: Sequence[UUID], since: DateTime) -> dict[UUID, DateTime]:
        latest: dict[UUID, DateTime] = {}
        for flow_run_id in flow_run_ids:
            beats = [beat for beat in self.heartbeats.get(flow_run_id, []) if beat >= since]
            if beats:
                latest[flow_run_id] = max(beats)
        return latest

    async def latest_event_occurred(self, since: DateTime) -> DateTime | None:
        if self.latest_event is None or self.latest_event < since:
            return None
        return self.latest_event


class TestZombieFlowRunReaper:
    async def test_crashes_a_run_that_stopped_sending_heartbeats(self) -> None:
        silent = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[silent], heartbeats={silent.id: [LONG_AGO]})

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == [silent.id]
        assert len(client.state_changes) == 1
        flow_run_id, state, force = client.state_changes[0]
        assert (flow_run_id, state.type, state.message, force) == (
            silent.id,
            StateType.CRASHED,
            "Flow run marked as crashed due to missing heartbeats.",
            False,
        )

    async def test_leaves_a_run_that_sent_a_heartbeat_within_the_window(self) -> None:
        alive = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[alive], heartbeats={alive.id: [LONG_AGO, RECENTLY]})

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == []
        assert client.state_changes == []

    async def test_leaves_a_run_that_never_sent_a_heartbeat(self) -> None:
        """Without heartbeats configured, no run is being watched, as before this check replaced the automation."""
        unwatched = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[unwatched])

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == []
        assert client.state_changes == []

    async def test_leaves_a_run_that_entered_its_running_state_within_the_window(self) -> None:
        resumed = make_running_run(running_since=RECENTLY)
        client = InMemoryZombieClient(flow_runs=[resumed], heartbeats={resumed.id: [RECENTLY]})

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == []
        assert client.state_changes == []

    async def test_measures_the_window_back_from_the_newest_stored_event(self) -> None:
        """A run whose last heartbeat is older than the window counts as alive while storing events lags behind."""
        storing_lag = timedelta(minutes=2)
        alive = make_running_run(running_since=LONG_AGO)
        last_stored_heartbeat = NOW - storing_lag - ZOMBIE_HEARTBEAT_WINDOW + timedelta(seconds=30)
        client = InMemoryZombieClient(
            flow_runs=[alive], heartbeats={alive.id: [last_stored_heartbeat]}, latest_event=NOW - storing_lag
        )

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == []
        assert client.state_changes == []

    async def test_judges_no_run_when_no_event_was_stored_within_the_window(self) -> None:
        silent = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[silent], heartbeats={silent.id: [LONG_AGO]}, latest_event=LONG_AGO)

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert (check.crashed, check.events_stored) == ([], False)
        assert client.state_changes == []

    async def test_does_not_report_a_run_that_finished_before_it_was_crashed(self) -> None:
        finished = make_running_run(running_since=LONG_AGO)
        silent = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(
            flow_runs=[finished, silent],
            heartbeats={finished.id: [LONG_AGO], silent.id: [LONG_AGO]},
            finished_meanwhile={finished.id},
        )

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == [silent.id]
        assert [flow_run_id for flow_run_id, _, _ in client.state_changes] == [finished.id, silent.id]

    async def test_judges_running_runs_beyond_the_first_page(self) -> None:
        silent_runs = [make_running_run(running_since=LONG_AGO) for _ in range(FLOW_RUNS_PAGE_SIZE + 1)]
        client = InMemoryZombieClient(flow_runs=silent_runs, heartbeats={run.id: [LONG_AGO] for run in silent_runs})

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == [run.id for run in silent_runs]

    async def test_crashes_an_in_process_retry_wait_whose_retry_was_due_before_the_window(self) -> None:
        """Only the process sleeping out an in-process retry can resume it, so a wait long past its due time is dead."""
        dead_wait = make_retry_wait(retry_due=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[dead_wait])

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == [dead_wait.id]

    async def test_leaves_a_retry_wait_whose_retry_was_due_within_the_window(self) -> None:
        resuming = make_retry_wait(retry_due=RECENTLY)
        client = InMemoryZombieClient(flow_runs=[resuming])

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == []
        assert client.state_changes == []

    async def test_leaves_a_rescheduled_retry_that_waits_for_a_worker(self) -> None:
        queued = make_retry_wait(retry_due=LONG_AGO, retry_type="reschedule")
        client = InMemoryZombieClient(flow_runs=[queued])

        check = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert check.crashed == []
        assert client.state_changes == []


@pytest.mark.parametrize(
    ("heartbeat_frequency_seconds", "expected"),
    [
        pytest.param(None, timedelta(minutes=3), id="heartbeats-off"),
        pytest.param(30, timedelta(minutes=3), id="default-frequency"),
        pytest.param(300, timedelta(minutes=30), id="slow-heartbeats"),
    ],
)
def test_heartbeat_window_follows_the_heartbeat_frequency(
    heartbeat_frequency_seconds: int | None, expected: timedelta
) -> None:
    assert heartbeat_window(heartbeat_frequency_seconds) == expected
