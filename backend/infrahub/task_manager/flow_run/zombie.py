from datetime import timedelta
from uuid import UUID

from prefect import State
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.types import DateTime

from infrahub.log import get_logger

from .prefect_client import ZombieReaperPrefectClient

ZOMBIE_HEARTBEAT_WINDOW = timedelta(minutes=3)
"""How long a flow run may go without a heartbeat after it should be running; flow runs send one every 30 seconds."""

ZOMBIE_CRASH_MESSAGE = "Flow run marked as crashed due to missing heartbeats."
FLOW_RUNS_PAGE_SIZE = 200
AWAITING_RETRY_STATE_NAME = "AwaitingRetry"
IN_PROCESS_RETRY = "in_process"


class ZombieFlowRunReaper:
    """Crash flow runs whose worker died without recording a final state."""

    def __init__(self, client: ZombieReaperPrefectClient, window: timedelta = ZOMBIE_HEARTBEAT_WINDOW) -> None:
        self.client = client
        self.window = window

    async def crash_zombies(self, now: DateTime) -> list[UUID]:
        """Crash the zombie flow runs as of `now` and return their IDs.

        A running run is a zombie when it entered its running state more than the window ago and
        sent no heartbeat within it. A run waiting out an in-process retry is one when its retry was
        due more than the window ago: the process sleeping out the delay is the only one that can
        resume it. The current state is read first, so a run that already finished is never touched.
        """
        silent_since = now - self.window
        candidates = [
            flow_run
            for flow_run in await self._read_all(StateType.RUNNING)
            if flow_run.state is not None and flow_run.state.timestamp <= silent_since
        ]
        candidates += [
            flow_run
            for flow_run in await self._read_all(StateType.SCHEDULED, state_name=AWAITING_RETRY_STATE_NAME)
            if self._retry_overdue(flow_run=flow_run, silent_since=silent_since)
        ]
        if not candidates:
            return []

        # A heartbeat missing from the stored events only means the run is dead if events are being stored.
        latest_event = await self.client.latest_event_occurred(since=silent_since)
        if latest_event is None:
            get_logger().warning(
                "Not judging flow runs for missing heartbeats because no event was stored within the window",
                window_seconds=self.window.total_seconds(),
            )
            return []

        heartbeating = await self.client.flow_runs_with_heartbeat_since(
            flow_run_ids=[flow_run.id for flow_run in candidates], since=silent_since
        )
        crashed: list[UUID] = []
        for flow_run in candidates:
            if flow_run.id in heartbeating:
                continue
            # Without force, orchestration refuses the transition for a run that finished meanwhile.
            final_state = await self.client.set_flow_run_state(
                flow_run_id=flow_run.id, state=State(type=StateType.CRASHED, message=ZOMBIE_CRASH_MESSAGE), force=False
            )
            if final_state == StateType.CRASHED:
                crashed.append(flow_run.id)
        return crashed

    @staticmethod
    def _retry_overdue(flow_run: FlowRun, silent_since: DateTime) -> bool:
        # A rescheduled retry waits for a worker to pick it up, which no heartbeat tells about.
        if flow_run.empirical_policy.retry_type != IN_PROCESS_RETRY or flow_run.state is None:
            return False
        scheduled_time = flow_run.state.state_details.scheduled_time
        return scheduled_time is not None and scheduled_time <= silent_since

    async def _read_all(self, state_type: StateType, state_name: str | None = None) -> list[FlowRun]:
        state_filter = FlowRunFilterState(type=FlowRunFilterStateType(any_=[state_type]))
        if state_name is not None:
            state_filter.name = FlowRunFilterStateName(any_=[state_name])
        flow_run_filter = FlowRunFilter(state=state_filter)
        flow_runs: list[FlowRun] = []
        while True:
            page = await self.client.read_flow_runs(
                flow_run_filter=flow_run_filter, limit=FLOW_RUNS_PAGE_SIZE, offset=len(flow_runs)
            )
            flow_runs.extend(page)
            if len(page) < FLOW_RUNS_PAGE_SIZE:
                return flow_runs
