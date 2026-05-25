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
from infrahub.events.group_action import (
    GroupAutoCreateCappedEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedEvent,
    GroupMemberAddedEvent,
)
from infrahub.events.models import EventMeta, EventNode, InfrahubEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeUpdatedEvent
from infrahub.external_protocols import ExternalAuthProtocol
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.events import dummy_event_meta, send_events
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

QUERY_GROUP_AUTO_CREATE_EVENTS = """
query($event_type: [String!]) {
  InfrahubEvent(event_type: $event_type, limit: 50) {
    count
    edges {
      node {
        id
        event
        __typename
        ... on GroupAutoCreatedEventType {
          idp
          triggering_user_id
          triggering_user_name
          protocol
          group_id
          group_name
          source_pattern
          origin_value
          payload
        }
        ... on GroupAutoCreateRejectedEventType {
          idp
          triggering_user_id
          triggering_user_name
          protocol
          rejected_claim_value
          payload
        }
        ... on GroupAutoCreateCappedEventType {
          idp
          triggering_user_id
          triggering_user_name
          protocol
          cap_value
          dropped_claims
          dropped_count
          payload
        }
      }
    }
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

_TEST_ID = uuid.uuid4().hex[:8]
BRANCH1_NAME = f"branch1-{_TEST_ID}"
BRANCH2_NAME = f"branch2-{_TEST_ID}"
BRANCH3_NAME = f"branch3-{_TEST_ID}"

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

    branch1 = Branch(uuid=branch1_id, name=BRANCH1_NAME)
    branch2 = Branch(uuid=branch2_id, name=BRANCH2_NAME)
    branch3 = Branch(uuid=branch3_id, name=BRANCH3_NAME)

    items: dict[str, InfrahubEvent] = {
        "branch1_created": BranchCreatedEvent(
            branch_name=BRANCH1_NAME,
            branch_id=str(branch1_id),
            sync_with_git=True,
            meta=dummy_event_meta(branch=branch1),
        ),
        "branch1_rebased": BranchRebasedEvent(
            branch_name=BRANCH1_NAME,
            branch_id=str(branch1_id),
            meta=dummy_event_meta(branch=branch1),
        ),
        "branch2_created": BranchCreatedEvent(
            branch_name=BRANCH2_NAME,
            branch_id=str(branch2_id),
            sync_with_git=False,
            meta=dummy_event_meta(branch=branch2),
        ),
        "branch2_rebased": BranchRebasedEvent(
            branch_name=BRANCH2_NAME,
            branch_id=str(branch2_id),
            meta=dummy_event_meta(branch=branch2),
        ),
        "branch3_created": BranchCreatedEvent(
            branch_name=BRANCH3_NAME,
            branch_id=str(branch3_id),
            sync_with_git=True,
            meta=dummy_event_meta(branch=branch3),
        ),
        "branch1_mutated1": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag1.get_id(),
            changelog=tag1.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_1).to_event_context(),
            ),
        ),
        "branch1_mutated2": NodeUpdatedEvent(
            kind="BuiltinTag",
            node_id=tag1_update.get_id(),
            changelog=tag1_update.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_1).to_event_context(),
            ),
        ),
        "branch1_mutated3": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag2.get_id(),
            changelog=tag2.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_1).to_event_context(),
            ),
        ),
        "branch1_mutated4": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag3.get_id(),
            changelog=tag3.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2).to_event_context(),
            ),
        ),
        "branch1_mutated5": NodeCreatedEvent(
            kind=group_eu.get_kind(),
            node_id=group_eu.get_id(),
            changelog=group_eu.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2).to_event_context(),
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
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2).to_event_context(),
            ),
        ),
        "branch1_mutated7": NodeCreatedEvent(
            kind=group_fr.get_kind(),
            node_id=group_fr.get_id(),
            changelog=group_fr.node_changelog,
            meta=EventMeta(
                branch=branch1,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch1, account=ACCOUNT_SESSION_2).to_event_context(),
            ),
        ),
        "branch2_mutated1": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag4.get_id(),
            changelog=tag4.node_changelog,
            meta=EventMeta(
                branch=branch2,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch2, account=ACCOUNT_SESSION_1).to_event_context(),
            ),
        ),
        "branch2_mutated2": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag5.get_id(),
            changelog=tag5.node_changelog,
            meta=EventMeta(
                branch=branch2,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch2, account=ACCOUNT_SESSION_2).to_event_context(),
            ),
        ),
        "branch2_mutated3": NodeCreatedEvent(
            kind="BuiltinTag",
            node_id=tag6.get_id(),
            changelog=tag6.node_changelog,
            meta=EventMeta(
                branch=branch2,
                account_id=ACCOUNT2_ID,
                context=InfrahubContext.init(branch=branch2, account=ACCOUNT_SESSION_2).to_event_context(),
            ),
        ),
        "branch3_mutated1": NodeCreatedEvent(
            kind="TestPerson",
            node_id=person1.get_id(),
            changelog=person1.node_changelog,
            meta=EventMeta(
                branch=branch3,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch3, account=ACCOUNT_SESSION_1).to_event_context(),
            ),
        ),
        "branch3_mutated2": NodeCreatedEvent(
            kind="TestPerson",
            node_id=person2.get_id(),
            changelog=person2.node_changelog,
            meta=EventMeta(
                branch=branch3,
                account_id=ACCOUNT1_ID,
                context=InfrahubContext.init(branch=branch3, account=ACCOUNT_SESSION_1).to_event_context(),
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
    """Because we can't guarantee that Prefect is empty at the start of the test easily.

    we need to exclude all events not created by this test suite.

    """
    filtered_events = [event for event in result_data["InfrahubEvent"]["edges"] if event["node"]["id"] in in_scope_ids]
    return {"InfrahubEvent": {"count": len(filtered_events), "edges": filtered_events}}


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None, None, None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


async def run_query(
    db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any], account_session: AccountSession
) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
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
    session_admin: AccountSession,
) -> None:
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={},
        account_session=session_admin,
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
        account_session=session_admin,
    )
    assert result.errors is None
    assert result.data

    result_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": BRANCH1_NAME},
        account_session=session_admin,
    )
    assert result_branch1.errors is None
    assert result_branch1.data

    clean_result = filter_outofscope_events(result_branch1.data, event_ids_inscope)
    assert clean_result["InfrahubEvent"]["count"] == 9

    result_count_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_SIMPLE_COUNT_EVENT,
        variables={"branch": BRANCH1_NAME},
        account_session=session_admin,
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
        account_session=session_admin,
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
        variables={"branch": BRANCH1_NAME, "account": ACCOUNT1_ID},
        account_session=session_admin,
    )
    assert branch1_account1.errors is None
    assert branch1_account1.data
    assert branch1_account1.data["InfrahubEvent"]["count"] == 3

    branch1_account2 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": BRANCH1_NAME, "account": ACCOUNT2_ID},
        account_session=session_admin,
    )
    assert branch1_account2.errors is None
    assert branch1_account2.data
    assert branch1_account2.data["InfrahubEvent"]["count"] == 4

    branch2_account1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": BRANCH2_NAME, "account": ACCOUNT1_ID},
        account_session=session_admin,
    )
    assert branch2_account1.errors is None
    assert branch2_account1.data
    assert branch2_account1.data["InfrahubEvent"]["count"] == 1

    branch2_account2 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": BRANCH2_NAME, "account": ACCOUNT2_ID},
        account_session=session_admin,
    )
    assert branch2_account2.errors is None
    assert branch2_account2.data
    assert branch2_account2.data["InfrahubEvent"]["count"] == 2

    paginated_account1_page1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"account": ACCOUNT1_ID, "limit": 4, "offset": 0},
        account_session=session_admin,
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
        account_session=session_admin,
    )
    assert paginated_account1_page2.errors is None
    assert paginated_account1_page2.data
    assert paginated_account1_page2.data["InfrahubEvent"]["count"] == 7
    assert len(paginated_account1_page2.data["InfrahubEvent"]["edges"]) == 3

    account1_branch1_branch3 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"account": ACCOUNT1_ID, "branch": [BRANCH1_NAME, BRANCH3_NAME]},
        account_session=session_admin,
    )
    assert account1_branch1_branch3.errors is None
    assert account1_branch1_branch3.data
    assert account1_branch1_branch3.data["InfrahubEvent"]["count"] == 6
    assert len(account1_branch1_branch3.data["InfrahubEvent"]["edges"]) == 6

    branch3_level_1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"level": 1, "branch": [BRANCH3_NAME]},
        account_session=session_admin,
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
        variables={"has_children": True, "branch": [BRANCH3_NAME]},
        account_session=session_admin,
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
        account_session=session_admin,
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
        variables={"event_type": ["infrahub.node.created"], "limit": 50},
        account_session=session_admin,
    )
    assert created_branch1.errors is None
    assert created_branch1.data
    clean_result = filter_outofscope_events(created_branch1.data, event_ids_inscope)
    assert clean_result["InfrahubEvent"]["count"] == 11
    assert [node["node"]["event"] for node in clean_result["InfrahubEvent"]["edges"]] == ["infrahub.node.created"] * 11

    all_branch1 = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": [BRANCH1_NAME]},
        account_session=session_admin,
    )
    assert all_branch1.errors is None
    assert all_branch1.data
    assert all_branch1.data["InfrahubEvent"]["count"] > 2
    occurred_at = all_branch1.data["InfrahubEvent"]["edges"][1]["node"]["occurred_at"]

    since_timestamp = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"branch": [BRANCH1_NAME], "since": occurred_at},
        account_session=session_admin,
    )
    assert since_timestamp.errors is None
    assert since_timestamp.data
    assert since_timestamp.data["InfrahubEvent"]["count"] == 2

    group_add_event = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_EVENT,
        variables={"event_type": ["infrahub.group.member_added"], "account": ACCOUNT2_ID},
        account_session=session_admin,
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
        account_session=session_admin,
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


@pytest.fixture
async def group_auto_create_events(
    default_branch: Branch,
    prefect_client: PrefectClient,
) -> dict[str, InfrahubEvent]:
    triggering_user_id = uuid.uuid4()
    triggering_user_name = f"alice-{_TEST_ID}"
    group_id = uuid.uuid4()
    idp_name = f"provider-{_TEST_ID}"

    items: dict[str, InfrahubEvent] = {
        "auto_created": GroupAutoCreatedEvent(
            idp=idp_name,
            triggering_user_id=triggering_user_id,
            triggering_user_name=triggering_user_name,
            protocol=ExternalAuthProtocol.OIDC,
            group_id=group_id,
            group_name=f"ops-admins-{_TEST_ID}",
            source_pattern=r"^(?P<name>ops-.*)$",
            origin_value=idp_name,
            meta=dummy_event_meta(branch=default_branch),
        ),
        "rejected_claim": GroupAutoCreateRejectedEvent(
            idp=idp_name,
            triggering_user_id=triggering_user_id,
            triggering_user_name=triggering_user_name,
            protocol=ExternalAuthProtocol.OIDC,
            rejected_claim_value="!!invalid-claim!!",
            meta=dummy_event_meta(branch=default_branch),
        ),
        "cap_breach": GroupAutoCreateCappedEvent(
            idp=idp_name,
            triggering_user_id=triggering_user_id,
            triggering_user_name=triggering_user_name,
            protocol=ExternalAuthProtocol.OAUTH2,
            cap_value=5,
            dropped_claims=["ops-extra-a", "ops-extra-b", "ops-extra-c"],
            dropped_count=3,
            meta=dummy_event_meta(branch=default_branch),
        ),
    }
    await send_events(client=prefect_client, events=list(items.values()))
    return items


async def test_event_query_group_auto_create(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    group_auto_create_events: dict[str, InfrahubEvent],
    session_admin: AccountSession,
) -> None:
    in_scope_ids = [str(event.meta.id) for event in group_auto_create_events.values()]

    created_event = group_auto_create_events["auto_created"]
    assert isinstance(created_event, GroupAutoCreatedEvent)
    rejected_event = group_auto_create_events["rejected_claim"]
    assert isinstance(rejected_event, GroupAutoCreateRejectedEvent)
    cap_event = group_auto_create_events["cap_breach"]
    assert isinstance(cap_event, GroupAutoCreateCappedEvent)

    created_result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_EVENTS,
        variables={"event_type": ["infrahub.group.auto_created"]},
        account_session=session_admin,
    )
    assert created_result.errors is None
    assert created_result.data
    created_edges = [
        edge for edge in created_result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids
    ]
    assert len(created_edges) == 1
    created_node = created_edges[0]["node"]
    assert created_node["event"] == "infrahub.group.auto_created"
    assert created_node["idp"] == created_event.idp
    assert created_node["triggering_user_id"] == str(created_event.triggering_user_id)
    assert created_node["triggering_user_name"] == created_event.triggering_user_name
    assert created_node["protocol"] == created_event.protocol.value
    assert created_node["group_id"] == str(created_event.group_id)
    assert created_node["group_name"] == created_event.group_name
    assert created_node["source_pattern"] == created_event.source_pattern
    assert created_node["origin_value"] == created_event.origin_value
    assert created_node["payload"]["data"]["group_name"] == created_event.group_name

    rejected_result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_EVENTS,
        variables={"event_type": ["infrahub.group.auto_create_rejected"]},
        account_session=session_admin,
    )
    assert rejected_result.errors is None
    assert rejected_result.data
    rejected_edges = [
        edge for edge in rejected_result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids
    ]
    assert len(rejected_edges) == 1
    rejected_node = rejected_edges[0]["node"]
    assert rejected_node["event"] == "infrahub.group.auto_create_rejected"
    assert rejected_node["idp"] == rejected_event.idp
    assert rejected_node["triggering_user_name"] == rejected_event.triggering_user_name
    assert rejected_node["protocol"] == rejected_event.protocol.value
    assert rejected_node["rejected_claim_value"] == rejected_event.rejected_claim_value

    cap_result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_EVENTS,
        variables={"event_type": ["infrahub.group.auto_create_capped"]},
        account_session=session_admin,
    )
    assert cap_result.errors is None
    assert cap_result.data
    cap_edges = [edge for edge in cap_result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids]
    assert len(cap_edges) == 1
    cap_node = cap_edges[0]["node"]
    assert cap_node["event"] == "infrahub.group.auto_create_capped"
    assert cap_node["idp"] == cap_event.idp
    assert cap_node["protocol"] == cap_event.protocol.value
    assert cap_node["cap_value"] == cap_event.cap_value
    assert cap_node["dropped_count"] == cap_event.dropped_count
    assert sorted(cap_node["dropped_claims"]) == sorted(cap_event.dropped_claims)


QUERY_GROUP_AUTO_CREATE_BY_FILTER = """
query($event_type_filter: EventTypeFilter) {
  InfrahubEvent(event_type_filter: $event_type_filter, limit: 50) {
    count
    edges {
      node {
        id
        event
        ... on GroupAutoCreatedEventType {
          idp
          protocol
        }
        ... on GroupAutoCreateRejectedEventType {
          idp
          protocol
        }
        ... on GroupAutoCreateCappedEventType {
          idp
          protocol
        }
      }
    }
  }
}
"""


@pytest.fixture
async def group_auto_create_events_mixed_idps(
    default_branch: Branch,
    prefect_client: PrefectClient,
) -> dict[str, InfrahubEvent]:
    triggering_user_id = uuid.uuid4()
    idp_a = f"provider-a-{_TEST_ID}"
    idp_b = f"provider-b-{_TEST_ID}"

    items: dict[str, InfrahubEvent] = {
        "a_oidc_created": GroupAutoCreatedEvent(
            idp=idp_a,
            triggering_user_id=triggering_user_id,
            triggering_user_name=f"alice-{_TEST_ID}",
            protocol=ExternalAuthProtocol.OIDC,
            group_id=uuid.uuid4(),
            group_name=f"a-oidc-{_TEST_ID}",
            source_pattern=r"^(?P<name>.*)$",
            origin_value=idp_a,
            meta=dummy_event_meta(branch=default_branch),
        ),
        "a_oauth2_rejected": GroupAutoCreateRejectedEvent(
            idp=idp_a,
            triggering_user_id=triggering_user_id,
            triggering_user_name=f"alice-{_TEST_ID}",
            protocol=ExternalAuthProtocol.OAUTH2,
            rejected_claim_value=f"bad-{_TEST_ID}",
            meta=dummy_event_meta(branch=default_branch),
        ),
        "b_oidc_created": GroupAutoCreatedEvent(
            idp=idp_b,
            triggering_user_id=triggering_user_id,
            triggering_user_name=f"bob-{_TEST_ID}",
            protocol=ExternalAuthProtocol.OIDC,
            group_id=uuid.uuid4(),
            group_name=f"b-oidc-{_TEST_ID}",
            source_pattern=r"^(?P<name>.*)$",
            origin_value=idp_b,
            meta=dummy_event_meta(branch=default_branch),
        ),
        "b_oauth2_cap_breach": GroupAutoCreateCappedEvent(
            idp=idp_b,
            triggering_user_id=triggering_user_id,
            triggering_user_name=f"bob-{_TEST_ID}",
            protocol=ExternalAuthProtocol.OAUTH2,
            cap_value=1,
            dropped_claims=[f"dropped-{_TEST_ID}"],
            dropped_count=1,
            meta=dummy_event_meta(branch=default_branch),
        ),
    }
    await send_events(client=prefect_client, events=list(items.values()))
    return items


async def test_event_query_group_auto_create_filter_by_idp(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    group_auto_create_events_mixed_idps: dict[str, InfrahubEvent],
    session_admin: AccountSession,
) -> None:
    in_scope_ids = {str(event.meta.id) for event in group_auto_create_events_mixed_idps.values()}
    idp_a = group_auto_create_events_mixed_idps["a_oidc_created"].idp

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_BY_FILTER,
        variables={"event_type_filter": {"group_auto_create": {"idp": [idp_a]}}},
        account_session=session_admin,
    )
    assert result.errors is None
    assert result.data

    edges = [edge for edge in result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids]
    returned_ids = {edge["node"]["id"] for edge in edges}
    assert returned_ids == {
        str(group_auto_create_events_mixed_idps["a_oidc_created"].meta.id),
        str(group_auto_create_events_mixed_idps["a_oauth2_rejected"].meta.id),
    }
    for edge in edges:
        assert edge["node"]["idp"] == idp_a


async def test_event_query_group_auto_create_filter_by_protocol(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    group_auto_create_events_mixed_idps: dict[str, InfrahubEvent],
    session_admin: AccountSession,
) -> None:
    in_scope_ids = {str(event.meta.id) for event in group_auto_create_events_mixed_idps.values()}

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_BY_FILTER,
        variables={"event_type_filter": {"group_auto_create": {"protocol": ["oidc"]}}},
        account_session=session_admin,
    )
    assert result.errors is None
    assert result.data

    edges = [edge for edge in result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids]
    returned_ids = {edge["node"]["id"] for edge in edges}
    assert returned_ids == {
        str(group_auto_create_events_mixed_idps["a_oidc_created"].meta.id),
        str(group_auto_create_events_mixed_idps["b_oidc_created"].meta.id),
    }
    for edge in edges:
        assert edge["node"]["protocol"] == "oidc"


async def test_event_query_group_auto_create_filter_idp_and_protocol(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    group_auto_create_events_mixed_idps: dict[str, InfrahubEvent],
    session_admin: AccountSession,
) -> None:
    in_scope_ids = {str(event.meta.id) for event in group_auto_create_events_mixed_idps.values()}
    idp_a = group_auto_create_events_mixed_idps["a_oidc_created"].idp

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_BY_FILTER,
        variables={"event_type_filter": {"group_auto_create": {"idp": [idp_a], "protocol": ["oidc"]}}},
        account_session=session_admin,
    )
    assert result.errors is None
    assert result.data

    edges = [edge for edge in result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids]
    returned_ids = {edge["node"]["id"] for edge in edges}
    assert returned_ids == {str(group_auto_create_events_mixed_idps["a_oidc_created"].meta.id)}


@pytest.fixture
async def auto_create_and_branch_events(
    default_branch: Branch,
    prefect_client: PrefectClient,
) -> dict[str, InfrahubEvent]:
    branch_for_event = Branch(uuid=uuid.uuid4(), name=f"empty-filter-{_TEST_ID}")
    items: dict[str, InfrahubEvent] = {
        "auto_created": GroupAutoCreatedEvent(
            idp=f"provider-empty-{_TEST_ID}",
            triggering_user_id=uuid.uuid4(),
            triggering_user_name=f"alice-{_TEST_ID}",
            protocol=ExternalAuthProtocol.OIDC,
            group_id=uuid.uuid4(),
            group_name=f"empty-{_TEST_ID}",
            source_pattern=r"^(?P<name>.*)$",
            origin_value=f"provider-empty-{_TEST_ID}",
            meta=dummy_event_meta(branch=default_branch),
        ),
        "branch_created": BranchCreatedEvent(
            branch_name=branch_for_event.name,
            branch_id=str(branch_for_event.get_uuid()),
            sync_with_git=True,
            meta=dummy_event_meta(branch=branch_for_event),
        ),
    }
    await send_events(client=prefect_client, events=list(items.values()))
    return items


async def test_event_query_group_auto_create_empty_filter_restricts_to_auto_create_events(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    auto_create_and_branch_events: dict[str, InfrahubEvent],
    session_admin: AccountSession,
) -> None:
    in_scope_ids = {str(event.meta.id) for event in auto_create_and_branch_events.values()}

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_GROUP_AUTO_CREATE_BY_FILTER,
        variables={"event_type_filter": {"group_auto_create": {}}},
        account_session=session_admin,
    )
    assert result.errors is None
    assert result.data

    edges = [edge for edge in result.data["InfrahubEvent"]["edges"] if edge["node"]["id"] in in_scope_ids]
    returned_ids = {edge["node"]["id"] for edge in edges}
    assert returned_ids == {str(auto_create_and_branch_events["auto_created"].meta.id)}
    auto_create_event_names = {
        GroupAutoCreatedEvent.event_name,
        GroupAutoCreateRejectedEvent.event_name,
        GroupAutoCreateCappedEvent.event_name,
    }
    for edge in edges:
        assert edge["node"]["event"] in auto_create_event_names
