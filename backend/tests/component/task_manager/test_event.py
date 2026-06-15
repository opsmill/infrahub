import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from tests.helpers.events import dummy_event_meta, extract_expected_ids, send_events

from infrahub.core.branch import Branch
from infrahub.events.branch_action import BranchCreatedEvent, BranchMergedEvent, BranchRebasedEvent
from infrahub.events.models import InfrahubEvent
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


def filter_outofscope_events(events: dict, in_scope_ids: list[str]) -> dict[str, Any]:
    """Because we can't guarantee that Prefect is empty at the start of the test easily.

    we need to exclude all events not created by this test suite.

    """
    filtered_events = [event for event in events["edges"] if event["node"]["id"] in in_scope_ids]
    return {"count": len(filtered_events), "edges": filtered_events}


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture(scope="module")
async def branch1_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def branch2_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def branch3_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
async def events_data(
    prefect_client: PrefectClient, branch1_id: str, branch2_id: str, branch3_id: str
) -> dict[str, InfrahubEvent]:
    branch1 = Branch(name="branch1", uuid=uuid.UUID(branch1_id))
    branch2 = Branch(name="branch2", uuid=uuid.UUID(branch2_id))
    # The branch name must contain characters that are SQL LIKE wildcards (`_`) to cover
    # label matching against values that require escaping.
    branch3 = Branch(name="branch_with_underscores", uuid=uuid.UUID(branch3_id))

    items: dict[str, InfrahubEvent] = {
        "branch1_created": BranchCreatedEvent(
            branch_name="branch1",
            branch_id=branch1_id,
            sync_with_git=True,
            meta=dummy_event_meta(branch=branch1),
        ),
        "branch1_rebased": BranchRebasedEvent(
            branch_name="branch1", branch_id=branch1_id, meta=dummy_event_meta(branch=branch1)
        ),
        "branch2_created": BranchCreatedEvent(
            branch_name="branch2",
            branch_id=branch2_id,
            sync_with_git=False,
            meta=dummy_event_meta(branch=branch2),
        ),
        "branch2_rebased": BranchRebasedEvent(
            branch_name="branch2", branch_id=branch2_id, meta=dummy_event_meta(branch=branch2)
        ),
        "branch3_merged": BranchMergedEvent(
            branch_name="branch_with_underscores", branch_id=branch3_id, meta=dummy_event_meta(branch=branch3)
        ),
    }

    await send_events(client=prefect_client, events=list(items.values()))
    return items


@pytest.fixture(scope="module")
async def event_ids_inscope(events_data: dict[str, InfrahubEvent]) -> list[str]:
    return [str(event.meta.id) for event in events_data.values()]


async def test_query_no_filters(event_ids_inscope: list[str]) -> None:
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    events = await PrefectEvent.query(fields=fields, event_filter=InfrahubEventFilter())
    clean_events = filter_outofscope_events(events, event_ids_inscope)
    assert clean_events["count"] == 5


async def test_query_branch_filter(events_data: dict[str, InfrahubEvent], event_ids_inscope: list[str]) -> None:
    expected_ids = extract_expected_ids(expected_events=["branch1_created", "branch1_rebased"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    event_filter = InfrahubEventFilter()
    event_filter.add_branch_filter(branches=["branch1"])
    events = await PrefectEvent.query(fields=fields, event_filter=event_filter)
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids


async def test_query_ids_filter(events_data: dict[str, InfrahubEvent], event_ids_inscope: list[str]) -> None:
    expected_ids = extract_expected_ids(expected_events=["branch1_created", "branch2_created"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    event_filter = InfrahubEventFilter()
    event_filter.add_event_id_filter(ids=expected_ids)

    events = await PrefectEvent.query(fields=fields, event_filter=event_filter)
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids


async def test_query_event_type_filter_branch_with_underscores(
    events_data: dict[str, InfrahubEvent], event_ids_inscope: list[str]
) -> None:
    """Resource labels containing SQL LIKE wildcards (`_`) must still match exactly."""
    expected_ids = extract_expected_ids(expected_events=["branch3_merged"], data=events_data)
    fields = {"count": None, "edges": {"node": {"event": None, "branch": None}}}
    event_filter = InfrahubEventFilter()
    event_filter.add_event_type_filter(event_type_filter={"branch_merged": {"branches": ["branch_with_underscores"]}})

    events = await PrefectEvent.query(fields=fields, event_filter=event_filter)
    clean_events = filter_outofscope_events(events, event_ids_inscope)

    received_ids = sorted([event["node"]["id"] for event in clean_events["edges"]])
    assert received_ids == expected_ids
