from dataclasses import dataclass, field
from datetime import UTC, timedelta
from typing import Any
from uuid import UUID, uuid4

from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import (
    ConcurrencyLimitStrategy,
    ConcurrencyOptions,
    DeploymentSchedule,
    FlowRun,
    StateType,
)
from prefect.client.schemas.responses import DeploymentResponse, GlobalConcurrencyLimitResponse
from prefect.client.schemas.schedules import CronSchedule
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.workflows.constants import WorkflowTag, WorkflowType

NOW = DateTime.now(tz=UTC)
INTERNAL_TAG = WorkflowTag.WORKFLOWTYPE.render(identifier=WorkflowType.INTERNAL.value)


class RecordingScheduledFlowClient:
    """A Prefect client that serves canned deployments and runs, and records every call made to it."""

    def __init__(
        self,
        deployments: list[DeploymentResponse] | None = None,
        flow_runs: list[FlowRun] | None = None,
        history: list[dict[str, Any]] | None = None,
        page_size: int | None = None,
    ) -> None:
        self._deployments = deployments or []
        self._flow_runs = flow_runs or []
        self._history = history or []
        self._page_size = page_size
        self.deployment_reads: list[tuple[int | None, int]] = []
        self.flow_run_reads: list[tuple[FlowRunFilter | None, int | None, FlowRunSort | None]] = []
        self.history_reads: list[dict[str, Any]] = []

    async def read_deployments(self, limit: int | None = None, offset: int = 0) -> list[DeploymentResponse]:
        self.deployment_reads.append((limit, offset))
        page_size = self._page_size if self._page_size is not None else limit
        end = len(self._deployments) if page_size is None else offset + page_size
        return self._deployments[offset:end]

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        self.flow_run_reads.append((flow_run_filter, limit, sort))
        return self._flow_runs[offset : offset + limit] if limit is not None else self._flow_runs[offset:]

    async def flow_run_history(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        self.history_reads.append(body)
        return self._history


@dataclass
class DeploymentSpec:
    name: str
    cron: str = "* * * * *"
    tags: list[str] | None = None
    active: bool = True
    created_ago: timedelta = timedelta(days=10)
    concurrency_limit: int | None = None
    collision_strategy: ConcurrencyLimitStrategy | None = None
    schedules: list[DeploymentSchedule] | None = None


def make_deployment(spec: DeploymentSpec) -> DeploymentResponse:
    deployment_id = uuid4()
    return DeploymentResponse(
        id=deployment_id,
        name=spec.name,
        flow_id=uuid4(),
        tags=spec.tags if spec.tags is not None else [INTERNAL_TAG],
        labels={},
        created=NOW - spec.created_ago,
        global_concurrency_limit=(
            GlobalConcurrencyLimitResponse(name=spec.name, limit=spec.concurrency_limit, active_slots=0)
            if spec.concurrency_limit is not None
            else None
        ),
        concurrency_options=(
            ConcurrencyOptions(collision_strategy=spec.collision_strategy) if spec.collision_strategy else None
        ),
        schedules=spec.schedules
        if spec.schedules is not None
        else [
            DeploymentSchedule(
                id=uuid4(), deployment_id=deployment_id, schedule=CronSchedule(cron=spec.cron), active=spec.active
            )
        ],
    )


@dataclass
class FlowRunSpec:
    state_type: StateType
    expected_start_time: DateTime
    name: str = "a-run"
    state_name: str | None = None
    start_time: DateTime | None = None
    end_time: DateTime | None = None
    flow_id: UUID = field(default_factory=uuid4)


def make_flow_run(spec: FlowRunSpec) -> FlowRun:
    return FlowRun(
        id=uuid4(),
        flow_id=spec.flow_id,
        name=spec.name,
        state_type=spec.state_type,
        state_name=spec.state_name,
        expected_start_time=spec.expected_start_time,
        start_time=spec.start_time,
        end_time=spec.end_time,
    )
