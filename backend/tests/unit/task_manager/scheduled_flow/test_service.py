from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.objects import (
    ConcurrencyLimitStrategy,
    ConcurrencyOptions,
    DeploymentSchedule,
    StateType,
)
from prefect.client.schemas.responses import DeploymentResponse, GlobalConcurrencyLimitResponse
from prefect.client.schemas.schedules import CronSchedule, IntervalSchedule

from infrahub.services.adapters.cache import InfrahubCache
from infrahub.task_manager.flow_run.tags import WorkflowTagDecoder
from infrahub.task_manager.scheduled_flow.models import (
    LatestRunInfo,
    RecentOutcomeCounts,
    ScheduledFlowHealth,
)
from infrahub.task_manager.scheduled_flow.service import ScheduledFlowService
from infrahub.workflows.constants import WorkflowTag, WorkflowType

NOW = datetime.now(tz=UTC)
INTERNAL_TAG = WorkflowTag.WORKFLOWTYPE.render(identifier=WorkflowType.INTERNAL.value)


class NoCache(InfrahubCache):
    """A cache that never serves a hit, so every query exercises the assembly path."""

    def __init__(self) -> None:
        self.written: dict[str, str] = {}

    async def delete(self, key: str) -> None:
        self.written.pop(key, None)

    async def get(self, key: str) -> str | None:
        return None

    async def get_values(self, keys: list[str]) -> list[str | None]:
        return [None for _ in keys]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        return []

    async def set(self, key: str, value: str, expires: object = None, not_exists: bool = False) -> bool:
        self.written[key] = value
        return True

    async def close_connection(self) -> None:
        return None


class RecordingCache(NoCache):
    """A cache that serves back whatever was last written to it."""

    async def get(self, key: str) -> str | None:
        return self.written.get(key)


class FakeScheduledFlowReader:
    """A reader whose run data is fixed per deployment, and that refuses to list individual runs."""

    def __init__(
        self,
        deployments: list[DeploymentResponse],
        latest_runs: dict[UUID, LatestRunInfo | None] | None = None,
        outcomes: dict[UUID, RecentOutcomeCounts] | None = None,
    ) -> None:
        self.deployments = deployments
        self.latest_runs = latest_runs or {}
        self.outcomes = outcomes or {}
        self.deployment_reads = 0

    async def read_deployments(self) -> list[DeploymentResponse]:
        self.deployment_reads += 1
        return self.deployments

    async def read_latest_executed_run(self, deployment_id: UUID, now: datetime) -> LatestRunInfo | None:
        return self.latest_runs.get(deployment_id)

    async def read_recent_outcomes(self, deployment_id: UUID, now: datetime) -> RecentOutcomeCounts:
        return self.outcomes.get(deployment_id, RecentOutcomeCounts(window_hours=24, counts={}))

    async def read_flow_runs(self, *args: object, **kwargs: object) -> list[object]:
        raise AssertionError("the outcome breakdown must be aggregated by Prefect, never read run by run")


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


def build_service(
    reader: FakeScheduledFlowReader,
    catalogue_crons: dict[str, str] | None = None,
    cache: InfrahubCache | None = None,
) -> ScheduledFlowService:
    return ScheduledFlowService(
        reader=reader,
        tag_decoder=WorkflowTagDecoder(),
        cache=cache or NoCache(),
        catalogue_crons=catalogue_crons if catalogue_crons is not None else {},
    )


async def test_flows_needing_attention_are_listed_first_then_by_name() -> None:
    healthy = make_deployment(DeploymentSpec(name="b-healthy"))
    overdue = make_deployment(DeploymentSpec(name="z-overdue"))
    failed = make_deployment(DeploymentSpec(name="a-failed"))
    paused = make_deployment(DeploymentSpec(name="a-paused", active=False))
    reader = FakeScheduledFlowReader(
        deployments=[healthy, overdue, failed, paused],
        latest_runs={
            healthy.id: LatestRunInfo(
                id=uuid4(), state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(seconds=20)
            ),
            overdue.id: LatestRunInfo(
                id=uuid4(), state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(days=3)
            ),
            failed.id: LatestRunInfo(
                id=uuid4(), state_type=StateType.FAILED, expected_start_time=NOW - timedelta(seconds=20)
            ),
            paused.id: None,
        },
    )

    result = await build_service(reader=reader).query()

    assert [(flow.name, flow.health) for flow in result.flows] == [
        ("z-overdue", ScheduledFlowHealth.OVERDUE),
        ("a-failed", ScheduledFlowHealth.FAILED),
        ("a-paused", ScheduledFlowHealth.PAUSED),
        ("b-healthy", ScheduledFlowHealth.HEALTHY),
    ]


async def test_catalogue_workflow_with_no_registered_deployment_is_reported_separately() -> None:
    registered = make_deployment(DeploymentSpec(name="git_repositories_sync"))
    reader = FakeScheduledFlowReader(deployments=[registered])

    result = await build_service(
        reader=reader,
        catalogue_crons={"git_repositories_sync": "* * * * *", "clean-up-deadlocks": "* * * * *"},
    ).query()

    assert [flow.name for flow in result.flows] == ["git_repositories_sync"]
    assert result.catalogue_only == ["clean-up-deadlocks"]


async def test_a_newly_added_scheduled_workflow_needs_no_code_change_to_appear() -> None:
    brand_new = make_deployment(DeploymentSpec(name="a-brand-new-scheduled-flow", cron="0 4 * * *"))
    reader = FakeScheduledFlowReader(deployments=[brand_new])

    result = await build_service(reader=reader, catalogue_crons={"a-brand-new-scheduled-flow": "0 4 * * *"}).query()

    assert [flow.name for flow in result.flows] == ["a-brand-new-scheduled-flow"]
    assert result.catalogue_only == []
    assert result.flows[0].cron == "0 4 * * *"
    assert result.flows[0].interval_seconds == 86400


async def test_deployment_without_a_workflow_type_tag_reports_an_unknown_type() -> None:
    untagged = make_deployment(DeploymentSpec(name="registered-outside-the-catalogue", tags=[]))
    reader = FakeScheduledFlowReader(deployments=[untagged])

    result = await build_service(reader=reader).query()

    assert result.flows[0].workflow_type is None


async def test_workflow_type_is_decoded_from_the_deployment_tags() -> None:
    deployment = make_deployment(
        DeploymentSpec(name="typed", tags=[WorkflowTag.WORKFLOWTYPE.render(identifier=WorkflowType.CORE.value)])
    )
    reader = FakeScheduledFlowReader(deployments=[deployment])

    result = await build_service(reader=reader).query()

    assert result.flows[0].workflow_type == WorkflowType.CORE


async def test_deployments_without_a_cron_schedule_are_not_listed() -> None:
    event_driven = make_deployment(DeploymentSpec(name="event-driven", schedules=[]))
    interval_based = make_deployment(
        DeploymentSpec(
            name="interval-based",
            schedules=[
                DeploymentSchedule(
                    id=uuid4(),
                    deployment_id=uuid4(),
                    schedule=IntervalSchedule(interval=timedelta(minutes=5)),
                    active=True,
                )
            ],
        )
    )
    reader = FakeScheduledFlowReader(deployments=[event_driven, interval_based])

    result = await build_service(reader=reader).query()

    assert result.flows == []


async def test_concurrency_settings_are_carried_so_a_cancelled_verdict_can_be_explained() -> None:
    deployment = make_deployment(
        DeploymentSpec(
            name="git_repositories_sync",
            concurrency_limit=1,
            collision_strategy=ConcurrencyLimitStrategy.CANCEL_NEW,
        )
    )
    reader = FakeScheduledFlowReader(
        deployments=[deployment],
        latest_runs={
            deployment.id: LatestRunInfo(
                id=uuid4(),
                state_type=StateType.CANCELLED,
                expected_start_time=NOW - timedelta(seconds=20),
                start_time=None,
            )
        },
    )

    result = await build_service(reader=reader).query()

    assert result.flows[0].concurrency_limit == 1
    assert result.flows[0].collision_strategy == ConcurrencyLimitStrategy.CANCEL_NEW
    assert result.flows[0].health == ScheduledFlowHealth.CANCELLED


async def test_the_outcome_breakdown_never_reads_individual_runs() -> None:
    deployment = make_deployment(DeploymentSpec(name="git_repositories_sync"))
    reader = FakeScheduledFlowReader(
        deployments=[deployment],
        # The every-minute steady state during a stall: everything due in the window went unclaimed.
        outcomes={
            deployment.id: RecentOutcomeCounts(
                window_hours=24, counts={StateType.SCHEDULED: 1440, StateType.COMPLETED: 0}
            )
        },
        latest_runs={
            deployment.id: LatestRunInfo(
                id=uuid4(), state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(days=3)
            )
        },
    )

    result = await build_service(reader=reader).query()

    assert result.flows[0].recent_outcomes.counts == {StateType.SCHEDULED: 1440, StateType.COMPLETED: 0}
    assert result.flows[0].recent_outcomes.total == 1440
    assert result.flows[0].health == ScheduledFlowHealth.OVERDUE


async def test_a_second_query_inside_the_ttl_is_served_from_the_cache() -> None:
    deployment = make_deployment(DeploymentSpec(name="git_repositories_sync"))
    reader = FakeScheduledFlowReader(
        deployments=[deployment],
        # Non-empty so the cached round trip has to survive the state-keyed breakdown, not just the
        # scalar fields.
        outcomes={
            deployment.id: RecentOutcomeCounts(
                window_hours=24, counts={StateType.SCHEDULED: 1440, StateType.COMPLETED: 2}
            )
        },
        latest_runs={
            deployment.id: LatestRunInfo(
                id=uuid4(),
                state_type=StateType.CANCELLED,
                state_name="Cancelled",
                expected_start_time=NOW - timedelta(seconds=20),
                start_time=None,
            )
        },
    )
    service = build_service(reader=reader, cache=RecordingCache())

    first = await service.query()
    second = await service.query()

    assert reader.deployment_reads == 1
    assert second == first
    assert second.flows[0].recent_outcomes.counts == {StateType.SCHEDULED: 1440, StateType.COMPLETED: 2}
    assert second.flows[0].recent_outcomes.total == 1442
    assert second.flows[0].health == ScheduledFlowHealth.CANCELLED


async def test_prefect_failures_propagate_rather_than_becoming_an_empty_list() -> None:
    class FailingReader(FakeScheduledFlowReader):
        async def read_deployments(self) -> list[DeploymentResponse]:
            raise ConnectionError("Prefect is unreachable")

    with pytest.raises(ConnectionError, match=r"^Prefect is unreachable$"):
        await build_service(reader=FailingReader(deployments=[])).query()
