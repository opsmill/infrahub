import uuid

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from tests.helpers.events import extract_expected_ids, send_events

from infrahub.events.branch_action import BranchCreateEvent, BranchRebaseEvent
from infrahub.events.models import InfrahubEvent
from infrahub.task_manager.event import PrefectEvent

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


def filter_outofscope_events(events: dict, in_scope_ids: list[str]):
    """
    Because we can't garantee that Prefect is empty at the start of the test easily
    we need to exclude all events not created by this test suite.
    """
    filtered_events = [event for event in events["edges"] if event["node"]["id"] in in_scope_ids]
    return {"count": len(filtered_events), "edges": filtered_events}


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture):
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture(scope="module")
async def branch1_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def branch2_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def events_data(prefect_client: PrefectClient, branch1_id, branch2_id) -> dict[str, InfrahubEvent]:
    items: dict[str, InfrahubEvent] = {
        "branch1_created": BranchCreateEvent(branch="branch1", branch_id=branch1_id, sync_with_git=True),
        "branch1_rebased": BranchRebaseEvent(branch="branch1", branch_id=branch1_id),
        "branch2_created": BranchCreateEvent(branch="branch2", branch_id=branch2_id, sync_with_git=False),
        "branch2_rebased": BranchRebaseEvent(branch="branch2", branch_id=branch2_id),
    }

    await send_events(client=prefect_client, events=items.values())
    return items


@pytest.fixture(scope="module")
async def event_ids_inscope(events_data: dict[str, InfrahubEvent]) -> list[str]:
    return [str(event.id) for event in events_data.values()]


async def test_query_no_filters(event_ids_inscope):
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    events = await PrefectEvent.query(fields=fields)
    clean_events = filter_outofscope_events(events, event_ids_inscope)
    assert clean_events["count"] == 4


@pytest.mark.xfail(reason="Was working with Prefect 3.1 but is failing with Prefect 3.0, need to investigate")
async def test_query_branch_filter(events_data, event_ids_inscope):
    expected_ids = extract_expected_ids(expected_events=["branch1_created", "branch1_rebased"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}

    events = await PrefectEvent.query(fields=fields, branch="branch1")
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids


async def test_query_ids_filter(events_data, event_ids_inscope):
    expected_ids = extract_expected_ids(expected_events=["branch1_created", "branch2_created"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}

    events = await PrefectEvent.query(fields=fields, ids=expected_ids)
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids
