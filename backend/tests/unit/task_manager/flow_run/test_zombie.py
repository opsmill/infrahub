from collections.abc import Sequence
from datetime import UTC, timedelta
from typing import Literal
from uuid import UUID, uuid4

from prefect import State
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import FlowRun, FlowRunPolicy, StateDetails, StateType
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.task_manager.flow_run.zombie import (
    FLOW_RUNS_PAGE_SIZE,
    ZOMBIE_CRASH_MESSAGE,
    ZOMBIE_HEARTBEAT_WINDOW,
    ZombieFlowRunReaper,
)

NOW = DateTime(2026, 11, 7, 12, 0, tzinfo=UTC)
LONG_AGO = NOW - ZOMBIE_HEARTBEAT_WINDOW - timedelta(minutes=10)
RECENTLY = NOW - ZOMBIE_HEARTBEAT_WINDOW / 2


def make_running_run(running_since: DateTime) -> FlowRun:
    return FlowRun(flow_id=uuid4(), name="run", state=State(type=StateType.RUNNING, timestamp=running_since))


def make_retry_wait(retry_due: DateTime, retry_type: Literal["in_process", "reschedule"] = "in_process") -> FlowRun:
    return FlowRun(
        flow_id=uuid4(),
        name="run",
        empirical_policy=FlowRunPolicy(retry_type=retry_type),
        state=State(
            type=StateType.SCHEDULED, name="AwaitingRetry", state_details=StateDetails(scheduled_time=retry_due)
        ),
    )


class InMemoryZombieClient:
    """Stores flow runs and heartbeat times the way the task manager reports them."""

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
        matching = [
            run
            for run in self.flow_runs
            if run.state is not None and run.state.type in types and (names is None or run.state.name in names)
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

    async def flow_runs_with_heartbeat_since(self, flow_run_ids: Sequence[UUID], since: DateTime) -> set[UUID]:
        return {
            flow_run_id
            for flow_run_id in flow_run_ids
            if any(heartbeat >= since for heartbeat in self.heartbeats.get(flow_run_id, []))
        }

    async def latest_event_occurred(self, since: DateTime) -> DateTime | None:
        if self.latest_event is None or self.latest_event < since:
            return None
        return self.latest_event


class TestZombieFlowRunReaper:
    async def test_crashes_a_run_that_sent_no_heartbeat_within_the_window(self) -> None:
        silent = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[silent], heartbeats={silent.id: [LONG_AGO]})

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == [silent.id]
        assert len(client.state_changes) == 1
        flow_run_id, state, force = client.state_changes[0]
        assert (flow_run_id, state.type, state.message, force) == (
            silent.id,
            StateType.CRASHED,
            ZOMBIE_CRASH_MESSAGE,
            False,
        )

    async def test_leaves_a_run_that_sent_a_heartbeat_within_the_window(self) -> None:
        alive = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[alive], heartbeats={alive.id: [LONG_AGO, RECENTLY]})

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == []
        assert client.state_changes == []

    async def test_leaves_a_run_that_entered_its_running_state_within_the_window(self) -> None:
        """A run resuming after a silent retry wait gets a full window before its heartbeats are judged."""
        resumed = make_running_run(running_since=RECENTLY)
        client = InMemoryZombieClient(flow_runs=[resumed], heartbeats={resumed.id: [LONG_AGO]})

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == []
        assert client.state_changes == []

    async def test_judges_no_run_when_no_event_was_stored_within_the_window(self) -> None:
        silent = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[silent], latest_event=LONG_AGO)

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == []
        assert client.state_changes == []

    async def test_does_not_report_a_run_that_finished_before_it_was_crashed(self) -> None:
        finished = make_running_run(running_since=LONG_AGO)
        silent = make_running_run(running_since=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[finished, silent], finished_meanwhile={finished.id})

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == [silent.id]
        assert [flow_run_id for flow_run_id, _, _ in client.state_changes] == [finished.id, silent.id]

    async def test_judges_running_runs_beyond_the_first_page(self) -> None:
        silent_runs = [make_running_run(running_since=LONG_AGO) for _ in range(FLOW_RUNS_PAGE_SIZE + 1)]
        client = InMemoryZombieClient(flow_runs=silent_runs)

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == [run.id for run in silent_runs]

    async def test_crashes_an_in_process_retry_wait_whose_retry_was_due_before_the_window(self) -> None:
        """Only the process sleeping out an in-process retry can resume it, so a wait long past its due time is dead."""
        dead_wait = make_retry_wait(retry_due=LONG_AGO)
        client = InMemoryZombieClient(flow_runs=[dead_wait])

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == [dead_wait.id]

    async def test_leaves_a_retry_wait_whose_retry_was_due_within_the_window(self) -> None:
        resuming = make_retry_wait(retry_due=RECENTLY)
        client = InMemoryZombieClient(flow_runs=[resuming])

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == []
        assert client.state_changes == []

    async def test_leaves_a_rescheduled_retry_that_waits_for_a_worker(self) -> None:
        queued = make_retry_wait(retry_due=LONG_AGO, retry_type="reschedule")
        client = InMemoryZombieClient(flow_runs=[queued])

        crashed = await ZombieFlowRunReaper(client=client).crash_zombies(now=NOW)

        assert crashed == []
        assert client.state_changes == []
