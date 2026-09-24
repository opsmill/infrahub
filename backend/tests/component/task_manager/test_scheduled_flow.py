from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import StateType
from tests.helpers.task_manager import setup_task_manager_once

from infrahub.services.adapters.cache import InfrahubCache
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.task_manager.flow_run.tags import WorkflowTagDecoder
from infrahub.task_manager.scheduled_flow.health import OVERDUE_INTERVAL_MULTIPLIER
from infrahub.task_manager.scheduled_flow.models import ScheduledFlowHealth, ScheduledFlowSummary
from infrahub.task_manager.scheduled_flow.reader import ScheduledFlowReader
from infrahub.task_manager.scheduled_flow.service import ScheduledFlowService
from infrahub.workflows.catalogue import WORKFLOWS

CATALOGUE_CRONS = {workflow.name: workflow.cron for workflow in WORKFLOWS if workflow.cron}


class NoCache(InfrahubCache):
    """A cache that never serves a hit, so each query reads the live deployment state."""

    async def delete(self, key: str) -> None:
        return None

    async def get(self, key: str) -> str | None:
        return None

    async def get_values(self, keys: list[str]) -> list[str | None]:
        return [None for _ in keys]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        return []

    async def set(self, key: str, value: str, expires: object = None, not_exists: bool = False) -> bool:
        return True

    async def close_connection(self) -> None:
        return None


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture
async def registered_deployments(prefect_client: PrefectClient) -> None:
    await setup_task_manager_once()


@pytest.fixture
async def scheduled_flows(prefect_client: PrefectClient, registered_deployments: None) -> list[ScheduledFlowSummary]:
    service = ScheduledFlowService(
        reader=ScheduledFlowReader(client=PrefectClientAdapter(prefect_client)),
        tag_decoder=WorkflowTagDecoder(),
        cache=NoCache(),
        catalogue_crons=CATALOGUE_CRONS,
    )
    result = await service.query()
    assert result.catalogue_only == []
    return result.flows


async def test_every_catalogue_workflow_carrying_a_cron_is_listed(
    scheduled_flows: list[ScheduledFlowSummary],
) -> None:
    assert sorted(flow.name for flow in scheduled_flows) == sorted(CATALOGUE_CRONS)


async def test_each_flow_reports_the_cron_the_catalogue_declares(
    scheduled_flows: list[ScheduledFlowSummary],
) -> None:
    assert {flow.name: flow.cron for flow in scheduled_flows} == CATALOGUE_CRONS


async def test_a_never_run_daily_flow_reports_never_run_rather_than_a_success_or_a_failure(
    scheduled_flows: list[ScheduledFlowSummary],
) -> None:
    daily = [flow for flow in scheduled_flows if flow.interval_seconds == 86400]
    assert daily

    for flow in daily:
        assert flow.latest_run is None
        assert flow.health == ScheduledFlowHealth.NEVER_RUN


async def test_flows_needing_attention_are_ordered_first(
    scheduled_flows: list[ScheduledFlowSummary],
) -> None:
    healths = [flow.health for flow in scheduled_flows]
    unhealthy = {ScheduledFlowHealth.OVERDUE, ScheduledFlowHealth.FAILED, ScheduledFlowHealth.CANCELLED}
    first_healthy = next((index for index, health in enumerate(healths) if health not in unhealthy), len(healths))

    assert all(health in unhealthy for health in healths[:first_healthy])


async def test_an_every_minute_flow_with_no_worker_never_reports_a_future_run_as_its_last(
    scheduled_flows: list[ScheduledFlowSummary],
) -> None:
    """Prefect pre-creates future SCHEDULED runs for an every-minute deployment.

    With no worker consuming them the flow has genuinely not executed, so it must never read as
    healthy off the back of a run that has not happened.
    """
    every_minute = [flow for flow in scheduled_flows if flow.interval_seconds == 60]
    assert every_minute

    now = datetime.now(tz=UTC)
    for flow in every_minute:
        if flow.latest_run is not None:
            assert flow.latest_run.state_type not in (StateType.SCHEDULED, StateType.PENDING)
            assert flow.latest_run.expected_start_time is not None
            assert flow.latest_run.expected_start_time <= now

        assert flow.deployment_created_at is not None
        overdue_window = timedelta(seconds=60 * OVERDUE_INTERVAL_MULTIPLIER)
        expected = (
            ScheduledFlowHealth.OVERDUE
            if now - flow.deployment_created_at >= overdue_window
            else ScheduledFlowHealth.NEVER_RUN
        )
        assert flow.health == expected
