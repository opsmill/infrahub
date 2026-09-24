from datetime import timedelta
from typing import Protocol
from uuid import UUID

from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterDeploymentId,
    FlowRunFilterExpectedStartTime,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.responses import DeploymentResponse
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.log import get_logger
from infrahub.task_manager.flow_run.prefect_client import ScheduledFlowPrefectClient

from .models import LatestRunInfo, RecentOutcomeCounts

log = get_logger()

RECENT_OUTCOME_WINDOW_HOURS = 24

# Excluded from the latest-run read: they describe a run that has not happened. Prefect's scheduler
# pre-creates roughly an hour of future SCHEDULED runs per schedule and keeps doing so with no
# worker alive, so including them would report a stalled flow as healthy indefinitely.
NOT_YET_EXECUTED_STATES = [StateType.SCHEDULED, StateType.PENDING]


class ScheduledFlowReaderProtocol(Protocol):
    async def read_deployments(self) -> list[DeploymentResponse]: ...

    async def read_latest_executed_run(self, deployment_id: UUID, now: DateTime) -> LatestRunInfo | None: ...

    async def read_recent_outcomes(self, deployment_id: UUID, now: DateTime) -> RecentOutcomeCounts: ...


class ScheduledFlowReader:
    """Read the deployment and run facts a scheduled-flow summary is built from."""

    def __init__(self, client: ScheduledFlowPrefectClient) -> None:
        self.client = client

    async def read_deployments(self) -> list[DeploymentResponse]:
        return await self.client.read_deployments()

    async def read_latest_executed_run(self, deployment_id: UUID, now: DateTime) -> LatestRunInfo | None:
        flow_run_filter = FlowRunFilter(
            deployment_id=FlowRunFilterDeploymentId(any_=[deployment_id]),
            expected_start_time=FlowRunFilterExpectedStartTime(before_=now),
            state=FlowRunFilterState(type=FlowRunFilterStateType(not_any_=NOT_YET_EXECUTED_STATES)),
        )
        runs = await self.client.read_flow_runs(
            flow_run_filter=flow_run_filter,
            limit=1,
            # Sorting on start_time would hide a run cancelled before it began, which is exactly the
            # collision outcome this view exists to surface.
            sort=FlowRunSort.EXPECTED_START_TIME_DESC,
        )
        if not runs:
            return None

        run = runs[0]
        return LatestRunInfo(
            id=run.id,
            state_type=run.state_type,
            state_name=run.state_name,
            expected_start_time=run.expected_start_time,
            start_time=run.start_time,
            end_time=run.end_time,
        )

    async def read_recent_outcomes(self, deployment_id: UUID, now: DateTime) -> RecentOutcomeCounts:
        window = timedelta(hours=RECENT_OUTCOME_WINDOW_HOURS)
        body = {
            "history_start": (now - window).isoformat(),
            "history_end": now.isoformat(),
            # One bucket spanning the whole window: the totals are wanted, not a time series.
            "history_interval_seconds": window.total_seconds(),
            "deployments": {"id": {"any_": [str(deployment_id)]}},
        }
        buckets = await self.client.flow_run_history(body)

        counts: dict[StateType, int] = {}
        for bucket in buckets:
            for state in bucket.get("states", []):
                try:
                    state_type = StateType(state["state_type"])
                except ValueError:
                    log.info(f"Ignoring unrecognised flow run state '{state['state_type']}'")
                    continue
                counts[state_type] = counts.get(state_type, 0) + int(state["count_runs"])

        return RecentOutcomeCounts(window_hours=RECENT_OUTCOME_WINDOW_HOURS, counts=counts)
