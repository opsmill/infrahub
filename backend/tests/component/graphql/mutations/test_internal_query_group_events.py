from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.events.group_action import GroupMutatedEvent
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

CREATE_QUERY_GROUP = """
mutation($name: String!, $group_type: String!, $query: String!, $member: String!, $subscriber: String!) {
    CoreGraphQLQueryGroupCreate(data: {
        name: { value: $name },
        group_type: { value: $group_type },
        query: { id: $query },
        members: [{ id: $member }],
        subscribers: [{ id: $subscriber }],
    }) {
        ok
        object { id }
    }
}
"""

CHANGE_SUBSCRIBERS = """
mutation($group: String!, $subscriber: String!) {
    %s(data: { id: $group, name: "subscribers", nodes: [{ id: $subscriber }] }) {
        ok
    }
}
"""


@dataclass
class QueryGroupCase:
    name: str
    group_type: str
    peers_get_events: bool


QUERY_GROUP_CASES = [
    QueryGroupCase(name="internal-query-group", group_type="internal", peers_get_events=False),
    QueryGroupCase(name="default-query-group", group_type="default", peers_get_events=True),
]


async def _run(
    db: InfrahubDatabase,
    branch: Branch,
    account_session: AccountSession,
    source: str,
    variables: dict[str, str],
) -> tuple[dict, MemoryInfrahubEvent]:
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch, service=service, account_session=account_session)
    result = await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    assert result.errors is None
    assert result.data
    assert gql_params.context.background
    await gql_params.context.background()
    return result.data, memory_event


def _events_by_node(memory_event: MemoryInfrahubEvent) -> set[tuple[str, str]]:
    summary: set[tuple[str, str]] = set()
    for event in memory_event.events:
        if isinstance(event, NodeMutatedEvent | GroupMutatedEvent):
            summary.add((event.event_name, event.node_id))
        else:
            summary.add((event.event_name, ""))
    return summary


async def _create_tag(db: InfrahubDatabase, name: str) -> Node:
    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name=name)
    await tag.save(db=db)
    return tag


async def _create_stored_query(db: InfrahubDatabase, name: str) -> Node:
    stored_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await stored_query.new(db=db, name=name, query="query { BuiltinTag { edges { node { id } } } }")
    await stored_query.save(db=db)
    return stored_query


@pytest.mark.parametrize("case", QUERY_GROUP_CASES, ids=lambda case: case.name)
async def test_creating_a_query_group_emits_peer_events_only_for_a_default_group(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    session_first_account: AccountSession,
    case: QueryGroupCase,
) -> None:
    member = await _create_tag(db=db, name=f"member-{case.name}")
    subscriber = await _create_tag(db=db, name=f"subscriber-{case.name}")
    stored_query = await _create_stored_query(db=db, name=f"query-{case.name}")

    data, memory_event = await _run(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        source=CREATE_QUERY_GROUP,
        variables={
            "name": f"group-{case.name}",
            "group_type": case.group_type,
            "query": stored_query.id,
            "member": member.id,
            "subscriber": subscriber.id,
        },
    )

    group_id = data["CoreGraphQLQueryGroupCreate"]["object"]["id"]
    group_events = {("infrahub.node.created", group_id), ("infrahub.group.member_added", group_id)}
    peer_events = {
        ("infrahub.node.updated", member.id),
        ("infrahub.node.updated", subscriber.id),
        ("infrahub.node.updated", stored_query.id),
    }
    assert _events_by_node(memory_event) == (group_events | peer_events if case.peers_get_events else group_events)


@pytest.mark.parametrize("case", QUERY_GROUP_CASES, ids=lambda case: case.name)
@pytest.mark.parametrize("mutation", ["RelationshipAdd", "RelationshipRemove"])
async def test_changing_query_group_subscribers_emits_peer_events_only_for_a_default_group(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
    case: QueryGroupCase,
    mutation: str,
) -> None:
    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace=namespace,
                name=name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
            for namespace, name in (("Core", "GraphQLQueryGroup"), ("Builtin", "Tag"))
        ],
    )
    subscriber = await _create_tag(db=db, name=f"subscriber-{case.name}")
    stored_query = await _create_stored_query(db=db, name=f"query-{case.name}")
    group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
    await group.new(
        db=db,
        name=f"group-{case.name}",
        group_type=case.group_type,
        query=stored_query,
        subscribers=[subscriber] if mutation == "RelationshipRemove" else [],
    )
    await group.save(db=db)

    _, memory_event = await _run(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        source=CHANGE_SUBSCRIBERS % mutation,
        variables={"group": group.id, "subscriber": subscriber.id},
    )

    group_events = {("infrahub.node.updated", group.id)}
    peer_events = {("infrahub.node.updated", subscriber.id)}
    assert _events_by_node(memory_event) == (group_events | peer_events if case.peers_get_events else group_events)
