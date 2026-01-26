import uuid

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from tests.helpers.events import extract_expected_ids, send_events

from infrahub.core.branch import Branch
from infrahub.events.branch_action import BranchCreatedEvent, BranchRebasedEvent
from infrahub.events.models import EventMeta, InfrahubEvent
from infrahub.task_manager.event import PrefectEvent
from infrahub.task_manager.models import InfrahubEventFilter

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
    Because we can't guarantee that Prefect is empty at the start of the test easily
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
    branch1 = Branch(name="branch1", uuid=uuid.UUID(branch1_id))
    branch2 = Branch(name="branch2", uuid=uuid.UUID(branch2_id))

    items: dict[str, InfrahubEvent] = {
        "branch1_created": BranchCreatedEvent(
            branch_name="branch1",
            branch_id=branch1_id,
            sync_with_git=True,
            meta=EventMeta.with_dummy_context(branch=branch1),
        ),
        "branch1_rebased": BranchRebasedEvent(
            branch_name="branch1", branch_id=branch1_id, meta=EventMeta.with_dummy_context(branch=branch1)
        ),
        "branch2_created": BranchCreatedEvent(
            branch_name="branch2",
            branch_id=branch2_id,
            sync_with_git=False,
            meta=EventMeta.with_dummy_context(branch=branch2),
        ),
        "branch2_rebased": BranchRebasedEvent(
            branch_name="branch2", branch_id=branch2_id, meta=EventMeta.with_dummy_context(branch=branch2)
        ),
    }

    await send_events(client=prefect_client, events=list(items.values()))
    return items


@pytest.fixture(scope="module")
async def event_ids_inscope(events_data: dict[str, InfrahubEvent]) -> list[str]:
    return [str(event.meta.id) for event in events_data.values()]


async def test_query_no_filters(event_ids_inscope) -> None:
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    events = await PrefectEvent.query(fields=fields, event_filter=InfrahubEventFilter())
    clean_events = filter_outofscope_events(events, event_ids_inscope)
    assert clean_events["count"] == 4


async def test_query_branch_filter(events_data, event_ids_inscope) -> None:
    expected_ids = extract_expected_ids(expected_events=["branch1_created", "branch1_rebased"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    event_filter = InfrahubEventFilter()
    event_filter.add_branch_filter(branches=["branch1"])
    events = await PrefectEvent.query(fields=fields, event_filter=event_filter)
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids


async def test_query_ids_filter(events_data, event_ids_inscope) -> None:
    expected_ids = extract_expected_ids(expected_events=["branch1_created", "branch2_created"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    event_filter = InfrahubEventFilter()
    event_filter.add_event_id_filter(ids=expected_ids)

    events = await PrefectEvent.query(fields=fields, event_filter=event_filter)
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids
