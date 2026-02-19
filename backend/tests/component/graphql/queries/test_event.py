import uuid
from collections.abc import AsyncGenerator
from typing import Any, Generator

import pytest
from graphql import ExecutionResult
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.branch_action import BranchCreatedEvent, BranchRebasedEvent
from infrahub.events.group_action import GroupMemberAddedEvent
from infrahub.events.models import EventMeta, EventNode, InfrahubEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.events import send_events
from tests.helpers.graphql import graphql

QUERY_EVENT = """
query(
    $branch: [String!],
    $account: [String!],
    $parent__ids: [String!],
    $limit: Int,
    $offset: Int
    $level: Int
    $has_children: Boolean
    $event_type: [String!]
    $since: DateTime
    $primary_node__ids: [String!]
    $order: EventSortOrder
) {
  InfrahubEvent(
    branches: $branch,
    account__ids: $account,
    limit: $limit,
    offset: $offset,
    level: $level
    has_children: $has_children
    parent__ids: $parent__ids
    primary_node__ids: $primary_node__ids
    event_type: $event_type
    since: $since
    order: $order
  ) {
    count
    edges {
      node {
        id
        event
        branch
        has_children
        parent_id
        level
        occurred_at
        related_nodes {
            id
            kind
        }
        ... on GroupEvent {
          ancestors {
            id
            kind
          }
          members {
            id
            kind
          }
        }
        ... on NodeMutatedEvent {
          branch
          event
          payload
          primary_node {
            id
            kind
          }
          attributes {
            action
            kind
            name
            value
            value_previous
          }
          relationships {
            name
            action
            peer {
              id
              kind
            }
          }
        }
      }
    }
  }
}
"""


QUERY_SIMPLE_COUNT_EVENT = """
query($branch: [String!]) {
  InfrahubEvent(branches: $branch) {
    count
  }
}
"""

QUERY_MUTATED_NODES = """
query MutatedNodes($id: [String!]) {
  InfrahubEvent(primary_node__ids: $id) {
    count
    edges {
      node {
        id
        level
        __typename
        ... on NodeMutatedEvent {
          branch
          event
          payload
          primary_node {
            id
            kind
          }
          attributes {
            action
            kind
            name
            value
            value_previous
          }
        }
      }
    }
  }
}
"""

ACCOUNT1_ID = "33b15615-649e-4e9e-89b0-85e187251f1f"
ACCOUNT2_ID = "518b434f-40bf-4b65-b700-04696535ca8e"

ACCOUNT_SESSION_1 = AccountSession(authenticated=True, account_id=ACCOUNT1_ID, auth_type=AuthType.API)
ACCOUNT_SESSION_2 = AccountSession(authenticated=True, account_id=ACCOUNT2_ID, auth_type=AuthType.API)


@pytest.fixture
async def branch1_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def branch2_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def branch3_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def events_data(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    car_person_schema: SchemaBranch,
    prefect_client: PrefectClient,
    branch1_id: uuid.UUID,
    branch2_id: uuid.UUID,
    branch3_id: uuid.UUID,
) -> dict[str, InfrahubEvent]:
    tag1 = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
    await tag1.new(db=db, name="red", description="The red tag")
    await tag1.save(db=db)

    tag1_update = await NodeManager.get_one(id=tag1.id, db=db, branch=default_branch)
    tag1_update.description.value = "This is an important tag"
    await tag1_update.save(db=db)

    tag2 = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
    await tag2.new(db=db, name="green", description="The green tag")
    await tag2.save(db=db)

    tag3 = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
    await tag3.new(db=db, name="blue", description="The blue tag")
    await tag3.save(db=db)

    tag4 = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
    await tag4.new(db=db, name="yellow", description="The yellow tag")
    await tag4.save(db=db)

    tag5 = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
    await tag5.new(db=db, name="black", description="The black tag")
    await tag5.save(db=db)

    tag6 = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
    await tag6.new(db=db, name="brown", description="The brown tag")
    await tag6.save(db=db)

    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, name="Alfred", height=160)
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, name="Sarah", height=174)
    await person2.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="Volvo", nbr_seats=5, is_electric=False, owner=person1.id)
    await car.save(db=db)

    group_fr = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await group_fr.new(db=db, name="France", members=[person1, person2])
    await group_fr.save(db=db)

    group_eu = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await group_eu.new(db=db, name="Europe", children=[group_fr])
    await group_eu.save(db=db)

    branch1 = Branch(uuid=branch1_id, name="branch1")
    branch2 = Branch(uuid=branch2_id, name="branch2")
    branch3 = Branch(uuid=branch3_id, name="branch3")

    items: dict[str, InfrahubEvent] = {
        "branch1_created": BranchCreatedEvent(
            branch_name="branch1",
            branch_id=str(branch1_id),
            sync_with_git=True,
            meta=EventMeta.with_dummy_context(branch=branch1),
        ),
        "branch1_rebased": BranchRebasedEvent(
            branch_name="branch1",
            branch_id=str(branch1_id),
            meta=EventMeta.with_dummy_context(branch=branch1),
        ),
        "branch2_created": BranchCreatedEvent(
            branch_name="branch2",
            branch_id=str(branch2_id),
            sync_with_git=False,
            meta=EventMeta.with_dummy_context(branch=branch2),
        ),
        "branch2_rebased": BranchRebasedEvent(
            branch_name="branch2",
            branch_id=str(branch2_id),
            meta=EventMeta.with_dummy_context(branch=branch2),
        ),
        "branch3_created": BranchCreatedEvent(
            branch_name="branch3",
            branch_id=str(branch3_id),
            sync_with_git=True,
            meta=EventMeta.with_dummy_context(branch=branch3),
        ),
        "branch1_mutated1": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag1.get_id(),
            changelog=tag1.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_1),
            ),
        ),
        "branch1_mutated2": NodeUpdatedEvent(
            kind="BuiltinTag",
            node_id=tag1_update.get_id(),
            changelog=tag1_update.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_1),
            ),
        ),
        "branch1_mutated3": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag2.get_id(),
            changelog=tag2.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_1),
            ),
        ),
        "branch1_mutated4": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag3.get_id(),
            changelog=tag3.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2),
            ),
        ),
        "branch1_mutated5": NodeCreatedEvent(
            kind=group_eu.get_kind(),
            node_id=group_eu.get_id(),
            changelog=group_eu.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2),
            ),
        ),
        "branch1_mutated6": GroupMemberAddedEvent(
            kind=group_fr.get_kind(),
            node_id=group_fr.get_id(),
            members=[
                EventNode(id=person1.get_id(), kind=person1.get_kind()),
                EventNode(id=person2.get_id(), kind=person2.get_kind()),
            ],
            ancestors=[EventNode(id=group_eu.get_id(), kind=group_eu.get_kind())],
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2),
            ),
        ),
        "branch1_mutated7": NodeCreatedEvent(
            kind=group_fr.get_kind(),
            node_id=group_fr.get_id(),
            changelog=group_fr.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2),
            ),
        ),
        "branch2_mutated1": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag4.get_id(),
            changelog=tag4.node_changelog,
            meta=EventMeta(
                branch=branch2,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch2, account=ACCOUNT_SESSION_1),
            ),
        ),
        "branch2_mutated2": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag5.get_id(),
            changelog=tag5.node_changelog,
            meta=EventMeta(
                branch=branch2,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch2, account=ACCOUNT_SESSION_2),
            ),
        ),
        "branch2_mutated3": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag6.get_id(),
            changelog=tag6.node_changelog,
            meta=EventMeta(
                branch=branch2,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch2, account=ACCOUNT_SESSION_2),
            ),
        ),
        "branch3_mutated1": NodeCreatedEvent(
            kind="TestPerson",
            node_id=person1.get_id(),
            changelog=person1.node_changelog,
            meta=EventMeta(
                branch=branch3,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch3, account=ACCOUNT_SESSION_1),
            ),
        ),
        "branch3_mutated2": NodeCreatedEvent(
            kind="TestPerson",
            node_id=person2.get_id(),
            changelog=person2.node_changelog,
            meta=EventMeta(
                branch=branch3,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch3, account=ACCOUNT_SESSION_1),
            ),
        ),
    }

    items["branch3_mutated3"] = NodeCreatedEvent(
        kind="TestCar",
        node_id=car.get_id(),
        changelog=car.node_changelog,
        meta=EventMeta.from_parent(items["branch3_mutated1"]),
    )

    await send_events(client=prefect_client, events=list(items.values()))
    return items


@pytest.fixture
async def event_ids_inscope(events_data: dict[str, InfrahubEvent]) -> list[str]:
    return [str(event.meta.id) for event in events_data.values()]


def filter_outofscope_events(result_data: dict, in_scope_ids: list[str]) -> dict[str, Any]:
    """
    Because we can't guarantee that Prefect is empty at the start of the test easily
    we need to exclude all events not created by this test suite.
    """
    filtered_events = [event for event in result_data["InfrahubEvent"]["edges"] if event["node"]["id"] in in_scope_ids]
    return {"InfrahubEvent": {"count": len(filtered_events), "edges": filtered_events}}


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None, None, None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


async def run_query(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def test_event_query_prefect(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    events_data: dict[str, InfrahubEvent],
    event_ids_inscope: list[str],
) -> None:
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={},
    )
    assert result.errors is None
    assert result.data

    clean_result = filter_outofscope_events(result.data, event_ids_inscope)
    assert clean_result["InfrahubEvent"]["count"] == 10

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"order": "ASC"},
    )
    assert result.errors is None
    assert result.data

    result_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": "branch1"},
    )
    assert result_branch1.errors is None
    assert result_branch1.data

    clean_result = filter_outofscope_events(result_branch1.data, event_ids_inscope)
    assert clean_result["InfrahubEvent"]["count"] == 9

    result_count_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_SIMPLE_COUNT_EVENT,
        variables={"branch": "branch1"},
    )
    assert result_count_branch1.errors is None
    assert result_count_branch1.data

    # Validate that the count query works even if there are no edges requested
    # Due to the workings of `filter_outofscope_events()` we can't use that here
    # we just want to ensure that the query itself is valid.
    assert result_count_branch1.data["InfrahubEvent"]["count"] > 0

    mutated_nodes = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_MUTATED_NODES,
        variables={"id": events_data["branch1_mutated1"].node_id},
    )
    assert mutated_nodes.errors is None
    assert mutated_nodes.data
    clean_result = filter_outofscope_events(mutated_nodes.data, event_ids_inscope)

    assert len(clean_result["InfrahubEvent"]["edges"]) == 2
    created = [
        entry for entry in clean_result["InfrahubEvent"]["edges"] if entry["node"]["event"] == "infrahub.node.created"
    ][0]
    updated = [
        entry for entry in clean_result["InfrahubEvent"]["edges"] if entry["node"]["event"] == "infrahub.node.updated"
    ][0]

    assert created["node"]["attributes"] == [
        {"action": "ADDED", "kind": "List", "name": "human_friendly_id", "value": "['red']", "value_previous": None},
        {"action": "ADDED", "kind": "Text", "name": "display_label", "value": "red", "value_previous": None},
        {"action": "ADDED", "kind": "Text", "name": "name", "value": "red", "value_previous": None},
        {"action": "ADDED", "kind": "Text", "name": "description", "value": "The red tag", "value_previous": None},
    ]
    assert created["node"]["level"] == 0
    assert created["node"]["primary_node"]["id"] == events_data["branch1_mutated1"].node_id
    assert created["node"]["primary_node"]["kind"] == "BuiltinTag"

    assert updated["node"]["attributes"] == [
        {
            "action": "UPDATED",
            "kind": "Text",
            "name": "description",
            "value": "This is an important tag",
            "value_previous": "The red tag",
        }
    ]
    assert created["node"]["primary_node"]["id"] == events_data["branch1_mutated2"].node_id
    assert created["node"]["primary_node"]["kind"] == "BuiltinTag"

    branch1_account1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": "branch1", "account": ACCOUNT1_ID},
    )
    assert branch1_account1.errors is None
    assert branch1_account1.data
    assert branch1_account1.data["InfrahubEvent"]["count"] == 3

    branch1_account2 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": "branch1", "account": ACCOUNT2_ID},
    )
    assert branch1_account2.errors is None
    assert branch1_account2.data
    assert branch1_account2.data["InfrahubEvent"]["count"] == 4

    branch2_account1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": "branch2", "account": ACCOUNT1_ID},
    )
    assert branch2_account1.errors is None
    assert branch2_account1.data
    assert branch2_account1.data["InfrahubEvent"]["count"] == 1

    branch2_account2 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": "branch2", "account": ACCOUNT2_ID},
    )
    assert branch2_account2.errors is None
    assert branch2_account2.data
    assert branch2_account2.data["InfrahubEvent"]["count"] == 2

    paginated_account1_page1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"account": ACCOUNT1_ID, "limit": 4, "offset": 0},
    )
    assert paginated_account1_page1.errors is None
    assert paginated_account1_page1.data
    assert paginated_account1_page1.data["InfrahubEvent"]["count"] == 7
    assert len(paginated_account1_page1.data["InfrahubEvent"]["edges"]) == 4

    paginated_account1_page2 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"account": ACCOUNT1_ID, "limit": 4, "offset": 4},
    )
    assert paginated_account1_page2.errors is None
    assert paginated_account1_page2.data
    assert paginated_account1_page2.data["InfrahubEvent"]["count"] == 7
    assert len(paginated_account1_page2.data["InfrahubEvent"]["edges"]) == 3

    account1_branch1_branch3 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"account": ACCOUNT1_ID, "branch": ["branch1", "branch3"]},
    )
    assert account1_branch1_branch3.errors is None
    assert account1_branch1_branch3.data
    assert account1_branch1_branch3.data["InfrahubEvent"]["count"] == 6
    assert len(account1_branch1_branch3.data["InfrahubEvent"]["edges"]) == 6

    branch3_level_1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"level": 1, "branch": ["branch3"]},
    )
    assert branch3_level_1.errors is None
    assert branch3_level_1.data
    assert branch3_level_1.data["InfrahubEvent"]["count"] == 1
    assert len(branch3_level_1.data["InfrahubEvent"]["edges"]) == 1
    assert len(branch3_level_1.data["InfrahubEvent"]["edges"][0]["node"]["related_nodes"]) == 1

    branch3_has_children_true = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"has_children": True, "branch": ["branch3"]},
    )
    assert branch3_has_children_true.errors is None
    assert branch3_has_children_true.data
    assert branch3_has_children_true.data["InfrahubEvent"]["count"] == 1
    assert len(branch3_has_children_true.data["InfrahubEvent"]["edges"]) == 1
    parent_node_id = branch3_has_children_true.data["InfrahubEvent"]["edges"][0]["node"]["id"]

    find_parent = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"parent__ids": [parent_node_id]},
    )
    assert find_parent.errors is None
    assert find_parent.data
    assert find_parent.data["InfrahubEvent"]["count"] == 1
    assert len(find_parent.data["InfrahubEvent"]["edges"]) == 1
    assert find_parent.data["InfrahubEvent"]["edges"][0]["node"]["parent_id"] == parent_node_id

    created_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"event_type": ["infrahub.node.created"]},
    )
    assert created_branch1.errors is None
    assert created_branch1.data
    assert created_branch1.data["InfrahubEvent"]["count"] == 11
    assert [node["node"]["event"] for node in created_branch1.data["InfrahubEvent"]["edges"]] == [
        "infrahub.node.created"
    ] * 10

    all_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": ["branch1"]},
    )
    assert all_branch1.errors is None
    assert all_branch1.data
    assert all_branch1.data["InfrahubEvent"]["count"] > 2
    occurred_at = all_branch1.data["InfrahubEvent"]["edges"][1]["node"]["occurred_at"]

    since_timestamp = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": ["branch1"], "since": occurred_at},
    )
    assert since_timestamp.errors is None
    assert since_timestamp.data
    assert since_timestamp.data["InfrahubEvent"]["count"] == 2

    group_add_event = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"event_type": ["infrahub.group.member_added"], "account": ACCOUNT2_ID},
    )
    assert group_add_event.errors is None
    assert group_add_event.data
    assert group_add_event.data["InfrahubEvent"]["count"] == 1
    members = [member["id"] for member in group_add_event.data["InfrahubEvent"]["edges"][0]["node"]["members"]]
    ancestors = [member["id"] for member in group_add_event.data["InfrahubEvent"]["edges"][0]["node"]["ancestors"]]
    assert len(members) == 2
    assert len(ancestors) == 1
    assert events_data["branch3_mutated1"].node_id in members
    assert events_data["branch3_mutated2"].node_id in members
    assert events_data["branch1_mutated5"].node_id in ancestors

    relationship_cardinality_many = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={
            "event_type": ["infrahub.node.created"],
            "primary_node__ids": events_data["branch1_mutated7"].node_id,
        },
    )
    assert not relationship_cardinality_many.errors
    assert relationship_cardinality_many.data
    assert relationship_cardinality_many.data["InfrahubEvent"]["count"] == 1
    event = relationship_cardinality_many.data["InfrahubEvent"]["edges"][0]["node"]
    assert len(event["relationships"]) == 2

    assert {
        "name": "members",
        "action": "ADDED",
        "peer": {"id": events_data["branch3_mutated1"].node_id, "kind": "TestPerson"},
    } in event["relationships"]
    assert {
        "name": "members",
        "action": "ADDED",
        "peer": {"id": events_data["branch3_mutated2"].node_id, "kind": "TestPerson"},
    } in event["relationships"]
