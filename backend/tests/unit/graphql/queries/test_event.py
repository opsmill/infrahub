import uuid
from typing import Any

import pytest
from graphql import ExecutionResult
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.events.branch_action import BranchCreatedEvent, BranchRebasedEvent
from infrahub.events.models import InfrahubEvent
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.events import send_events
from tests.helpers.graphql import graphql

QUERY_EVENT = """
query {
  InfrahubEvent {
    count
    edges {
      node {
        id
        event
        branch
      }
    }
  }
}
"""


@pytest.fixture(scope="module")
async def branch1_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def branch2_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def events_data(prefect_client: PrefectClient, branch1_id, branch2_id) -> dict[str, InfrahubEvent]:
    items: dict[str, InfrahubEvent] = {
        "branch1_created": BranchCreatedEvent(branch_name="branch1", branch_id=branch1_id, sync_with_git=True),
        "branch1_rebased": BranchRebasedEvent(branch_name="branch1", branch_id=branch1_id),
        "branch2_created": BranchCreatedEvent(branch_name="branch2", branch_id=branch2_id, sync_with_git=False),
        "branch2_rebased": BranchRebasedEvent(branch_name="branch2", branch_id=branch2_id),
    }

    await send_events(client=prefect_client, events=items.values())
    return items


@pytest.fixture(scope="module")
async def event_ids_inscope(events_data: dict[str, InfrahubEvent]) -> list[str]:
    return [str(event.id) for event in events_data.values()]


def filter_outofscope_events(result_data: dict, in_scope_ids: list[str]):
    """
    Because we can't garantee that Prefect is empty at the start of the test easily
    we need to exclude all events not created by this test suite.
    """
    filtered_events = [event for event in result_data["InfrahubEvent"]["edges"] if event["node"]["id"] in in_scope_ids]
    return {"InfrahubEvent": {"count": len(filtered_events), "edges": filtered_events}}


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture):
    async with get_client(sync_client=False) as client:
        yield client


async def run_query(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]) -> ExecutionResult:
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def test_event_query_prefect(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, events_data, event_ids_inscope
):
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={},
    )
    assert result.errors is None
    assert result.data

    clean_result = filter_outofscope_events(result.data, event_ids_inscope)
    assert clean_result["InfrahubEvent"]["count"] == 4
