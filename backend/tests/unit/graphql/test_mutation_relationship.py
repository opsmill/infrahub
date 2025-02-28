from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub_sdk.uuidt import UUIDT

from infrahub.auth import AccountSession, AuthType
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase
from infrahub.events.group_action import GroupMemberAddedEvent, GroupMemberRemovedEvent
from infrahub.events.models import EventNode
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.permissions import LocalPermissionBackend
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase


async def test_relationship_add(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
):
    await _define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="Builtin",
                name="Tag",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
            ObjectPermission(
                namespace="Test",
                name="Person",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
        tag_black_main.id,
    )

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    node_event = memory_event.events[0]
    assert isinstance(node_event, NodeMutatedEvent)
    assert node_event.data.node_id == person_jack_main.id
    relationship = node_event.data.relationships["tags"]
    assert isinstance(relationship, RelationshipCardinalityManyChangelog)
    peers = [peer.peer_id for peer in relationship.peers]
    assert len(peers) == 2
    assert tag_blue_main.id in peers
    assert tag_black_main.id in peers

    p1 = await NodeManager.get_one(db=db, id=person_jack_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_blue_main.id,
            tag_black_main.id,
        ]
    )

    # --------------------------------------
    # Add a Third member
    # --------------------------------------
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
        tag_red_main.id,
    )

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_blue_main.id,
            tag_black_main.id,
            tag_red_main.id,
        ]
    )

    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    node_event = memory_event.events[0]
    assert isinstance(node_event, NodeMutatedEvent)
    assert node_event.data.node_id == person_jack_main.id
    relationship = node_event.data.relationships["tags"]
    assert isinstance(relationship, RelationshipCardinalityManyChangelog)
    peers = [peer.peer_id for peer in relationship.peers]
    assert len(peers) == 1
    assert tag_red_main.id in peers


async def test_relationship_remove(
    db: InfrahubDatabase,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_tags_main.id,
        tag_blue_main.id,
        tag_black_main.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_tags_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_red_main.id,
        ]
    )

    # --------------------------------------
    # remove the second one
    # --------------------------------------
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_tags_main.id,
        tag_red_main.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_tags_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert [tag.peer_id for tag in tags] == sorted([])


async def test_relationship_wrong_name(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "notvalid",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == "'notvalid' is not a valid relationship for 'TestPerson'"

    # Relationship existing relationship with the wrong cardinality
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "primary_tag",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == "'primary_tag' must be a relationship of cardinality Many"


async def test_relationship_wrong_node(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    # Non existing Node
    bad_uuid = str(UUIDT())
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        bad_uuid,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == f"'{bad_uuid}': Unable to find the node in the database."

    # Wrong Kind
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        person_jack_main.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert (
        result.errors[0].message == f"'{person_jack_main.id}' 'TestPerson' is not a valid peer for '{InfrahubKind.TAG}'"
    )


async def test_relationship_groups_add(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_generics_data: dict[str, Node],
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
):
    await _define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="Core",
                name="StandardGroup",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value,
            ),
            ObjectPermission(
                namespace="Test",
                name="ElectricCar",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value,
            ),
            ObjectPermission(
                namespace="Test",
                name="GazCar",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2, c3])
    await g2.save(db=db)

    g1_root = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1_root.new(db=db, name="group1_root", children=[g1])
    await g1_root.save(db=db)

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "members",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        c2.id,
    )
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 2

    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    group_event = memory_event.events[0]
    assert isinstance(group_event, GroupMemberAddedEvent)
    assert [member.id for member in group_event.members] == [c2.id]
    assert group_event.members == [EventNode(id=c2.id, kind=c2.get_kind())]
    assert group_event.ancestors == [EventNode(id=g1_root.id, kind=g1_root.get_kind())]

    g_root = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g_root.new(db=db, name="root-group", children=[g2, g1_root])
    await g_root.save(db=db)

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 3

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 2

    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    group_event = memory_event.events[0]
    assert isinstance(group_event, GroupMemberAddedEvent)
    # While we mutated the relationship for c3 we expect the group member event to reflect that of the g1
    # group as c3 was already a member of g2 we don't see an event for that entry
    assert group_event.node_id == g1.id
    assert [member.id for member in group_event.members] == [c3.id]
    assert len(group_event.ancestors) == 2
    assert EventNode(id=g1_root.id, kind=g1_root.get_kind()) in group_event.ancestors
    assert EventNode(id=g_root.id, kind=g_root.get_kind()) in group_event.ancestors


async def test_relationship_groups_remove(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_generics_data,
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
):
    await _define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="Core",
                name="StandardGroup",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value,
            ),
            ObjectPermission(
                namespace="Test",
                name="ElectricCar",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value,
            ),
            ObjectPermission(
                namespace="Test",
                name="GazCar",
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value,
            ),
        ],
    )
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2, c3])
    await g2.save(db=db)

    g_root = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g_root.new(db=db, name="group1_root", children=[g1])
    await g_root.save(db=db)

    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "members",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        c1.id,
    )

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)

    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 0

    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    group_event = memory_event.events[0]
    assert isinstance(group_event, GroupMemberRemovedEvent)
    assert [member.id for member in group_event.members] == [c1.id]
    assert group_event.ancestors == [EventNode(id=g_root.id, kind=g_root.get_kind())]

    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)

    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, service=service, account_session=session_first_account
    )

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 0

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1

    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    group_event = memory_event.events[0]
    assert isinstance(group_event, GroupMemberRemovedEvent)
    # The c3 node is not member of g1 so we only expect to see a group event for the g2 group
    assert group_event.node_id == g2.id
    assert [member.id for member in group_event.members] == [c3.id]
    assert group_event.ancestors == []


async def test_relationship_groups_add_remove(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2])
    await g2.save(db=db)

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 8

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 2

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 8

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 1

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 8

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 2

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 8

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 1

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1


async def test_relationship_add_busy(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    p2 = car_person_generics_data["p2"]

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "cars",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        p2.id,
        c1.id,
    )

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert "'TestElectricCar' is already related to another peer on 'owner'" in str(result.errors[0])


async def test_relationship_add_from_pool(
    db: InfrahubDatabase, default_branch: Branch, prefix_pool_01: dict[str, Node]
):
    hugh = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await hugh.new(db=db, name="Hugh Jackman")
    await hugh.save(db=db)

    query = """
    mutation {
        RelationshipAdd(
            data: {
                id: "%s",
                name: "%s",
                nodes: [
                    {
                        from_pool: {
                            id: "%s"
                        }
                    }
                ]
            }
        ) {
            ok
        }
    }
    """ % (hugh.id, "ip_prefixes", prefix_pool_01["prefix_pool"].id)

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, root_value=None, variable_values={}
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=hugh.id, branch=default_branch)

    prefixes = await p1.ip_prefixes.get(db=db)
    addresses = await p1.ip_addresses.get(db=db)
    assert prefixes
    assert not addresses


# See #4649
async def test_add_generic_related_node_with_hfid(
    db: InfrahubDatabase,
    default_branch: Branch,
    generic_car_person_schema,
):
    electric_car = await Node.init(db=db, schema="TestElectricCar", branch=default_branch)
    await electric_car.new(db=db, name="testing-car", color="blue")
    await electric_car.save(db=db)

    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="testing-person")
    await person.save(db=db)

    query = """
    mutation {
        TestPersonUpdate(data: {
            id: "%s",
            car: {
                hfid: ["testing-car", "blue"],
                kind: "TestElectricCar"
              }
        }) {
            ok
            object {
                id
                car {
                    node {
                        name {
                            value
                        }
                    }
                }
            }
        }
    }
    """ % (person.id)

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    assert result.data["TestPersonUpdate"]["object"]["car"]["node"]["name"]["value"] == "testing-car"


async def test_with_permissions(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    first_account: CoreAccount,
    person_jack_main: Node,
    tag_blue_main: Node,
):
    registry.permission_backends = [LocalPermissionBackend()]

    permissions = []
    for object_permission in [
        ObjectPermission(
            namespace="Builtin",
            name="Tag",
            action=PermissionAction.UPDATE.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
        ObjectPermission(
            namespace="Test",
            name="Person",
            action=PermissionAction.UPDATE.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(
            db=db,
            namespace=object_permission.namespace,
            name=object_permission.name,
            action=object_permission.action,
            decision=object_permission.decision,
        )
        await obj.save(db=db)
        permissions.append(obj)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="chief-people-officer", permissions=permissions)
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="hr", roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": first_account.id})
    await group.members.save(db=db)

    first_session = AccountSession(
        authenticated=True, account_id=first_account.id, session_id=str(uuid4()), auth_type=AuthType.JWT
    )

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """

    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=first_session
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query % (person_jack_main.id, tag_blue_main.id),
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None


async def test_without_permissions(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    first_account: CoreAccount,
    person_jack_main: Node,
    tag_red_main: Node,
):
    registry.permission_backends = [LocalPermissionBackend()]

    first_session = AccountSession(
        authenticated=True, account_id=first_account.id, session_id=str(uuid4()), auth_type=AuthType.JWT
    )

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """

    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=first_session
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query % (person_jack_main.id, tag_red_main.id),
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert "You do not have one of the following permissions" in result.errors[0].message


async def _define_permissions(account: Node, db: InfrahubDatabase, object_permissions: list[ObjectPermission]) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    permissions = []
    for object_permission in object_permissions:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(
            db=db,
            namespace=object_permission.namespace,
            name=object_permission.name,
            action=object_permission.action,
            decision=object_permission.decision,
        )
        await obj.save(db=db)
        permissions.append(obj)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="chief-people-officer", permissions=permissions)
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="hr", roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": account.id})
    await group.members.save(db=db)
