from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from graphql import ExecutionResult
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.workers.dependencies import clear_singletons
from infrahub.workflows.catalogue import WORKFLOWS
from tests.helpers.graphql import graphql
from tests.helpers.task_manager import setup_task_manager_once

CATALOGUE_CRONS = {workflow.name: workflow.cron for workflow in WORKFLOWS if workflow.cron}

QUERY_SCHEDULED_FLOWS = """
query {
  InfrahubScheduledFlows {
    count
    catalogue_only
    edges {
      node {
        deployment_id
        name
        workflow_type
        cron
        timezone
        interval_seconds
        next_run_at
        active
        concurrency_limit
        collision_strategy
        health
        deployment_created_at
        latest_run {
          id
          state
          state_name
          expected_start_time
          start_time
          end_time
        }
        recent_outcomes {
          window_hours
          total
          counts {
            state
            count
          }
        }
      }
    }
  }
}
"""


@pytest.fixture(autouse=True)
def cache_singleton_with_redis_settings(redis: dict[int, int] | None) -> Generator[None, None, None]:
    """The scheduled-flow query caches its assembled result through the process-wide cache singleton.

    Drop the singleton so it is rebuilt against this module's redis settings, and drop it again
    afterwards so later modules do not inherit it.
    """
    clear_singletons()
    yield
    clear_singletons()


@pytest.fixture
async def prefect_client(prefect_test_fixture: Generator[None, None, None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture
async def registered_deployments(prefect_client: PrefectClient) -> None:
    await setup_task_manager_once()


async def run_query(db: InfrahubDatabase, branch: Branch) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=QUERY_SCHEDULED_FLOWS,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


@pytest.fixture
async def scheduled_flow_nodes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    registered_deployments: None,
) -> list[dict[str, Any]]:
    result = await run_query(db=db, branch=default_branch)

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubScheduledFlows"]["catalogue_only"] == []
    assert result.data["InfrahubScheduledFlows"]["count"] == len(CATALOGUE_CRONS)
    return [edge["node"] for edge in result.data["InfrahubScheduledFlows"]["edges"]]


async def test_every_scheduled_workflow_is_returned_with_its_cron(
    scheduled_flow_nodes: list[dict[str, Any]],
) -> None:
    assert {node["name"]: node["cron"] for node in scheduled_flow_nodes} == CATALOGUE_CRONS


async def test_the_workflow_type_and_health_enums_serialize_to_their_graphql_names(
    scheduled_flow_nodes: list[dict[str, Any]],
) -> None:
    assert {node["workflow_type"] for node in scheduled_flow_nodes} == {"INTERNAL"}
    # Nothing consumes the schedules in this test, so each flow is either late or too young to be.
    assert {node["health"] for node in scheduled_flow_nodes} <= {"OVERDUE", "NEVER_RUN"}


async def test_the_outcome_breakdown_is_a_typed_list_rather_than_an_untyped_map(
    scheduled_flow_nodes: list[dict[str, Any]],
) -> None:
    for node in scheduled_flow_nodes:
        outcomes = node["recent_outcomes"]
        assert outcomes["window_hours"] == 24
        assert isinstance(outcomes["counts"], list)
        assert outcomes["total"] == sum(entry["count"] for entry in outcomes["counts"])
        for entry in outcomes["counts"]:
            assert set(entry) == {"state", "count"}


async def test_a_flow_that_has_not_executed_reports_no_latest_run(
    scheduled_flow_nodes: list[dict[str, Any]],
) -> None:
    for node in scheduled_flow_nodes:
        assert node["latest_run"] is None
        assert node["deployment_created_at"] is not None
        assert node["active"] is True
        assert node["interval_seconds"] in (60, 86400)
        assert node["next_run_at"] is not None


async def test_concurrency_settings_are_exposed_so_a_cancelled_verdict_can_be_explained(
    scheduled_flow_nodes: list[dict[str, Any]],
) -> None:
    by_name = {node["name"]: node for node in scheduled_flow_nodes}

    assert by_name["git_repositories_sync"]["collision_strategy"] == "CANCEL_NEW"
    assert by_name["webhook-configure"]["collision_strategy"] == "ENQUEUE"
