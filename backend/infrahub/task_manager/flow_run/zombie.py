from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from prefect import State
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterNextScheduledStartTime,
    FlowRunFilterStartTime,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.types import DateTime

from .prefect_client import ZombieReaperPrefectClient

ZOMBIE_HEARTBEAT_WINDOW = timedelta(minutes=3)
"""Shortest time a flow run may go without a heartbeat before it is crashed."""

ZOMBIE_MISSED_HEARTBEATS = 6
"""Heartbeat intervals a flow run may miss before it is crashed, when that is longer than the shortest window."""

ZOMBIE_CRASH_MESSAGE = "Flow run marked as crashed due to missing heartbeats."
FLOW_RUNS_PAGE_SIZE = 200
AWAITING_RETRY_STATE_NAME = "AwaitingRetry"
IN_PROCESS_RETRY = "in_process"


def heartbeat_window(heartbeat_frequency_seconds: int | None) -> timedelta:
    """Return how long a flow run may go without a heartbeat for the configured heartbeat frequency."""
    if heartbeat_frequency_seconds is None:
        return ZOMBIE_HEARTBEAT_WINDOW
    return max(ZOMBIE_HEARTBEAT_WINDOW, timedelta(seconds=heartbeat_frequency_seconds * ZOMBIE_MISSED_HEARTBEATS))


@dataclass
class ZombieCheck:
    crashed: list[UUID] = field(default_factory=list)
    events_stored: bool = True
    """False when no event was stored within the window, in which case no run was judged."""


class ZombieFlowRunReaper:
    """Crash flow runs whose worker died without recording a final state."""

    def __init__(self, client: ZombieReaperPrefectClient, window: timedelta = ZOMBIE_HEARTBEAT_WINDOW) -> None:
        self.client = client
        self.window = window

    async def crash_zombies(self, now: DateTime) -> ZombieCheck:
        """Crash the zombie flow runs as of `now`.

        A running run is a zombie when it has sent heartbeats, has been running longer than the window and sent no
        heartbeat within it. A run waiting out an in-process retry is one when its retry was due more than the window
        ago: the process sleeping out the delay is the only one that can resume it. The current state is read first,
        so a run that already finished is never touched.
        """
        newest_event = await self.client.latest_event_occurred(since=now - self.window)
        if newest_event is None:
            return ZombieCheck(events_stored=False)
        # Measured back from the newest stored event, so a delay in storing events never makes a live run look silent.
        silent_since = min(now, newest_event) - self.window

        running = [
            flow_run
            for flow_run in await self._read_all(
                state_filter=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.RUNNING])),
                flow_run_filter=FlowRunFilter(start_time=FlowRunFilterStartTime(before_=silent_since)),
            )
            if flow_run.state is not None and flow_run.state.timestamp <= silent_since
        ]
        retry_waits = [
            flow_run
            for flow_run in await self._read_all(
                state_filter=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.SCHEDULED]),
                    name=FlowRunFilterStateName(any_=[AWAITING_RETRY_STATE_NAME]),
                ),
                flow_run_filter=FlowRunFilter(
                    next_scheduled_start_time=FlowRunFilterNextScheduledStartTime(before_=silent_since)
                ),
            )
            if self._retry_overdue(flow_run=flow_run, silent_since=silent_since)
        ]
        candidates = running + retry_waits
        if not candidates:
            return ZombieCheck()

        earliest_start = min(flow_run.start_time or silent_since for flow_run in candidates)
        last_heartbeats = await self.client.latest_heartbeats(
            flow_run_ids=[flow_run.id for flow_run in candidates], since=min(earliest_start, silent_since)
        )
        retry_wait_ids = {flow_run.id for flow_run in retry_waits}
        check = ZombieCheck()
        for flow_run in candidates:
            last_heartbeat = last_heartbeats.get(flow_run.id)
            if last_heartbeat is not None and last_heartbeat >= silent_since:
                continue
            # A run that never sent a heartbeat was never being watched; heartbeats may be turned off.
            if last_heartbeat is None and flow_run.id not in retry_wait_ids:
                continue
            # Without force, orchestration refuses the transition for a run that finished meanwhile.
            final_state = await self.client.set_flow_run_state(
                flow_run_id=flow_run.id, state=State(type=StateType.CRASHED, message=ZOMBIE_CRASH_MESSAGE), force=False
            )
            if final_state == StateType.CRASHED:
                check.crashed.append(flow_run.id)
        return check

    @staticmethod
    def _retry_overdue(flow_run: FlowRun, silent_since: DateTime) -> bool:
        # A rescheduled retry waits for a worker to pick it up, which no heartbeat tells about.
        if flow_run.empirical_policy.retry_type != IN_PROCESS_RETRY or flow_run.state is None:
            return False
        scheduled_time = flow_run.state.state_details.scheduled_time
        return scheduled_time is not None and scheduled_time <= silent_since

    async def _read_all(self, state_filter: FlowRunFilterState, flow_run_filter: FlowRunFilter) -> list[FlowRun]:
        flow_run_filter.state = state_filter
        flow_runs: list[FlowRun] = []
        while True:
            page = await self.client.read_flow_runs(
                flow_run_filter=flow_run_filter, limit=FLOW_RUNS_PAGE_SIZE, offset=len(flow_runs)
            )
            flow_runs.extend(page)
            if len(page) < FLOW_RUNS_PAGE_SIZE:
                return flow_runs
