from datetime import datetime
from uuid import UUID

from prefect.client.schemas.objects import StateType
from pydantic import BaseModel, Field

from infrahub.utils import InfrahubStringEnum
from infrahub.workflows.constants import WorkflowType


class ScheduledFlowHealth(InfrahubStringEnum):
    HEALTHY = "healthy"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"
    NEVER_RUN = "never_run"
    NO_RECENT_RUNS = "no_recent_runs"
    PAUSED = "paused"


class LatestRunInfo(BaseModel):
    """The newest run a deployment was due to start by now that got past the queue.

    Never carries a SCHEDULED or PENDING state: those are excluded by the read, because Prefect
    pre-creates future runs continuously and an unbounded read would name a run that has not happened.
    """

    id: UUID
    state_type: StateType | None = None
    state_name: str | None = None
    expected_start_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class RecentOutcomeCounts(BaseModel):
    """Per-state run tallies over a recent window, aggregated by Prefect rather than by reading runs."""

    window_hours: int
    counts: dict[StateType, int] = Field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


class ScheduledFlowSummary(BaseModel):
    deployment_id: UUID
    name: str
    workflow_type: WorkflowType | None = None
    cron: str
    timezone: str | None = None
    interval_seconds: int | None = None
    next_run_at: datetime | None = None
    active: bool
    concurrency_limit: int | None = None
    collision_strategy: str | None = None
    latest_run: LatestRunInfo | None = None
    recent_outcomes: RecentOutcomeCounts
    health: ScheduledFlowHealth
    deployment_created_at: datetime | None = None


class ScheduledFlowQueryResult(BaseModel):
    flows: list[ScheduledFlowSummary] = Field(default_factory=list)
    catalogue_only: list[str] = Field(default_factory=list)
