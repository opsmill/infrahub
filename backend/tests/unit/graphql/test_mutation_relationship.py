from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub_sdk.uuidt import UUIDT

from infrahub.auth import AccountSession, AuthType
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog
from infrahub.core.constants import InfrahubKind, MetadataOptions, PermissionAction, PermissionDecision, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.core.group import core_group, core_standard_group
from infrahub.database import InfrahubDatabase
from infrahub.events.group_action import GroupMemberAddedEvent, GroupMemberRemovedEvent
from infrahub.events.models import EventNode
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase


async def test_relationship_add(
    db: InfrahubDatabase,
    default_permission_backend: None,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    await define_permissions(
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
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch, service=service, account_session=session_first_account
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
    assert node_event.changelog.node_id == person_jack_main.id
    relationship = node_event.changelog.relationships["tags"]
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
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch, service=service, account_session=session_first_account
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
    assert node_event.changelog.node_id == person_jack_main.id
    relationship = node_event.changelog.relationships["tags"]
    assert isinstance(relationship, RelationshipCardinalityManyChangelog)
    peers = [peer.peer_id for peer in relationship.peers]
    assert len(peers) == 1
    assert tag_red_main.id in peers


async def test_relationship_remove(
    db: InfrahubDatabase,
    default_permission_backend: None,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
) -> None:
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

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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
) -> None:
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

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == "'notvalid' is not a valid relationship for 'TestPerson' at name"

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

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == "'primary_tag' must be a relationship of cardinality Many at name"


async def test_relationship_wrong_node(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
) -> None:
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

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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
    default_permission_backend: None,
    default_branch: Branch,
    car_person_generics_data: dict[str, Node],
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    await define_permissions(
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
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
    default_permission_backend: None,
    default_branch: Branch,
    car_person_generics_data,
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    await define_permissions(
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
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


async def test_relationship_groups_add_remove(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data
) -> None:
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2])
    await g2.save(db=db)

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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
    assert len(members) == 1

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1

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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
    assert len(members) == 1

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1


async def test_relationship_add_busy(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data) -> None:
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert "'TestElectricCar' is already related to another peer on 'owner'" in str(result.errors[0])


async def test_relationship_add_for_node_with_migrated_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema,
    car_person_schema: Node,
    person_alfred_main: Node,
) -> None:
    schema = SchemaRoot(generics=[core_group], nodes=[core_standard_group])
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    branch = await create_branch(db=db, branch_name="migrated-branch")
    schema = registry.schema.get_schema_branch(name=branch.name)
    person_schema = schema.get(name="TestPerson")
    person_schema.name = "GreatPerson"
    new_person_kind = "TestGreatPerson"
    assert person_schema.kind == new_person_kind
    registry.schema.set(name=new_person_kind, schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_person_kind, field_name="name"),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors
    core_node_schema = schema.get_generic(name="CoreNode")
    core_node_schema.used_by.append(new_person_kind)
    schema.set(name="CoreNode", schema=core_node_schema)
    await registry.schema.load_schema_to_db(db=db, schema=schema, branch=branch)

    # create group on main
    main_group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await main_group.new(
        db=db,
        name="main-group",
    )
    await main_group.save(db=db)
    # create group on branch
    branch_group = await Node.init(db=db, branch=branch, schema=InfrahubKind.STANDARDGROUP)
    await branch_group.new(
        db=db,
        name="branch-group",
    )
    await branch_group.save(db=db)

    # add person to group on main
    add_members_query = """
    mutation ($group_id: String!, $members: [RelatedNodeInput]) {
        RelationshipAdd(data: {
            id: $group_id,
            name: "members",
            nodes: $members,
        }) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=add_members_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"group_id": main_group.id, "members": [{"id": person_alfred_main.id}]},
    )
    assert not result.errors

    # add person to group on branch
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=add_members_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"group_id": branch_group.id, "members": [{"id": person_alfred_main.id}]},
    )
    assert not result.errors

    # check relationship count on main
    group_members_query = """
    query getRelationshipCount_CoreStandardGroup_members ($ids: [ID!]!) {
        CoreStandardGroup(
            ids: $ids
        ) {
            edges {
                node {
                    members {
                        count
                    }
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=group_members_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"ids": [main_group.id]},
    )
    assert not result.errors
    assert result.data
    assert result.data["CoreStandardGroup"]["edges"][0]["node"]["members"]["count"] == 1

    # check relationship count on branch
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=group_members_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"ids": [branch_group.id]},
    )
    assert not result.errors
    assert result.data
    assert result.data["CoreStandardGroup"]["edges"][0]["node"]["members"]["count"] == 1

    # check person-side relationship on main
    person_main = await NodeManager.get_one(db=db, id=person_alfred_main.id, branch=default_branch)
    groups = await person_main.member_of_groups.get(db=db)
    assert len(groups) == 1
    assert groups[0].peer_id == main_group.id
    main_person_schema = registry.schema.get(name="TestPerson", branch=default_branch, duplicate=False)
    members_rel_schema = main_person_schema.get_relationship("member_of_groups")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[person_alfred_main.id],
        source_kind="TestPerson",
        schema=members_rel_schema,
        filters={},
        branch=default_branch,
    )
    assert peer_count == 1

    # check group-side relationship on main
    group_main = await NodeManager.get_one(db=db, id=main_group.id, branch=default_branch)
    members = await group_main.members.get(db=db)
    assert len(members) == 1
    assert members[0].peer_id == person_alfred_main.id
    main_group_schema = registry.schema.get(name="CoreStandardGroup", branch=default_branch, duplicate=False)
    members_rel_schema = main_group_schema.get_relationship("members")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[main_group.id],
        source_kind="CoreStandardGroup",
        schema=members_rel_schema,
        filters={},
        branch=default_branch,
    )
    assert peer_count == 1

    # check person-side relationship on branch
    alfred_branch = await NodeManager.get_one(db=db, id=person_alfred_main.id, branch=branch)
    groups = await alfred_branch.member_of_groups.get(db=db)
    assert len(groups) == 1
    assert groups[0].peer_id == branch_group.id
    branch_person_schema = registry.schema.get(name="TestGreatPerson", branch=branch, duplicate=False)
    members_rel_schema = branch_person_schema.get_relationship("member_of_groups")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[person_alfred_main.id],
        source_kind="TestGreatPerson",
        schema=members_rel_schema,
        filters={},
        branch=branch,
    )
    assert peer_count == 1

    # check group-side relationship on branch
    group_branch = await NodeManager.get_one(db=db, id=branch_group.id, branch=branch)
    members = await group_branch.members.get(db=db)
    assert len(members) == 1
    assert members[0].peer_id == person_alfred_main.id
    branch_group_schema = registry.schema.get(name="CoreStandardGroup", branch=branch, duplicate=False)
    members_rel_schema = branch_group_schema.get_relationship("members")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[branch_group.id],
        source_kind="CoreStandardGroup",
        schema=members_rel_schema,
        filters={},
        branch=branch,
    )
    assert peer_count == 1


async def test_relationship_add_from_pool(
    db: InfrahubDatabase, default_branch: Branch, prefix_pool_01: dict[str, Node]
) -> None:
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
) -> None:
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

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
    default_permission_backend: None,
    register_core_models_schema: None,
    default_branch: Branch,
    first_account: CoreAccount,
    person_jack_main: Node,
    tag_blue_main: Node,
) -> None:
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=first_session)
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
    default_permission_backend: None,
    register_core_models_schema: None,
    default_branch: Branch,
    first_account: CoreAccount,
    person_jack_main: Node,
    tag_red_main: Node,
) -> None:
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=first_session)
    result = await graphql(
        schema=gql_params.schema,
        source=query % (person_jack_main.id, tag_red_main.id),
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert "You do not have one of the following permissions" in result.errors[0].message


async def test_relationship_read_only(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    """Validates that it's not possible to modify relationships that are read-only."""
    raw_schema = {
        "version": "1.0",
        "generics": [
            {
                "name": "Generic",
                "namespace": "Location",
                "hierarchical": True,
                "attributes": [{"name": "name", "optional": False, "kind": "Text"}],
                "relationships": [
                    {
                        "name": "devices",
                        "peer": "InfraDevice",
                        "cardinality": "many",
                        "optional": True,
                        "read_only": True,
                    }
                ],
            }
        ],
        "nodes": [
            {
                "name": "Device",
                "namespace": "Infra",
                "attributes": [{"name": "name", "kind": "Text", "optional": False}],
                "relationships": [
                    {"name": "location", "peer": "LocationGeneric", "optional": False, "cardinality": "one"}
                ],
            },
            {
                "name": "Site",
                "namespace": "Location",
                "inherit_from": ["LocationGeneric"],
                "attributes": [{"name": "description", "optional": False, "kind": "Text"}],
            },
        ],
    }
    schema = SchemaRoot(**raw_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    site_schema = schema_branch.get_node(name="LocationSite")
    device_schema = schema_branch.get_node(name="InfraDevice")

    site1 = await Node.init(db=db, schema=site_schema, branch=default_branch)
    await site1.new(db=db, name="site1", description="test")
    await site1.save(db=db)

    device1 = await Node.init(db=db, schema=device_schema, branch=default_branch)
    await device1.new(db=db, name="device1", location=site1)
    await device1.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    add_query = """
    mutation RelationshipAdd(
        $id: String!,
        $relationship_name: String!,
        $node: String!,
        ) {
        RelationshipAdd(
            data: {id: $id, name: $relationship_name, nodes: {id: $node}}
        ) {
        ok
        }
    }
    """
    add_result = await graphql(
        schema=gql_params.schema,
        source=add_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": site1.id, "relationship_name": "devices", "node": device1.id},
    )

    remove_query = """
    mutation RelationshipRemove(
        $id: String!,
        $relationship_name: String!,
        $node: String!,
        ) {
        RelationshipRemove(
            data: {id: $id, name: $relationship_name, nodes: {id: $node}}
        ) {
        ok
        }
    }
    """
    remove_result = await graphql(
        schema=gql_params.schema,
        source=remove_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": site1.id, "relationship_name": "devices", "node": device1.id},
    )

    assert add_result.errors
    assert "'devices' is a read-only relationship at LocationSite" in str(add_result.errors)

    assert remove_result.errors
    assert "'devices' is a read-only relationship at LocationSite" in str(remove_result.errors)


async def test_relationship_add_remove_profiles(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: None
) -> None:
    """Validates that profiles are applied when adding/removing profiles to a node."""
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John Doe")
    await person.save(db=db)

    person_initial = await NodeManager.get_one(db=db, id=person.id, branch=default_branch)
    assert person_initial.height.value is None
    assert person_initial.height.is_default is True
    assert person_initial.height.is_from_profile is False

    profile_schema = registry.schema.get("ProfileTestPerson", branch=default_branch)
    profile = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await profile.new(db=db, profile_name="tall-person", profile_priority=100, height=185)
    await profile.save(db=db)

    profile_check = await NodeManager.get_one(db=db, id=profile.id, branch=default_branch)
    assert profile_check.height.value == 185

    add_query = """
    mutation RelationshipAdd(
        $id: String!,
        $relationship_name: String!,
        $node: String!,
        ) {
        RelationshipAdd(
            data: {id: $id, name: $relationship_name, nodes: [{id: $node}]}
        ) {
        ok
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=add_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": person.id, "relationship_name": "profiles", "node": profile.id},
    )

    assert result.errors is None

    person_check = await NodeManager.get_one(db=db, id=person.id, branch=default_branch)
    profiles = await person_check.profiles.get(db=db)
    assert len(profiles) == 1
    assert profiles[0].peer_id == profile.id

    person_updated = await NodeManager.get_one(
        db=db, id=person.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert person_updated.height.value == 185
    assert person_updated.height.is_default is False
    assert person_updated.height.is_from_profile is True
    source = await person_updated.height.get_source(db=db)
    assert source is not None
    assert source.id == profile.id

    remove_query = """
    mutation RelationshipRemove(
        $id: String!,
        $relationship_name: String!,
        $node: String!,
        ) {
        RelationshipRemove(
            data: {id: $id, name: $relationship_name, nodes: [{id: $node}]}
        ) {
        ok
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=remove_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": person.id, "relationship_name": "profiles", "node": profile.id},
    )

    assert result.errors is None

    person_final = await NodeManager.get_one(
        db=db, id=person.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert person_final.height.value is None
    assert person_final.height.is_default is True
    assert person_final.height.is_from_profile is False
    source = await person_final.height.get_source(db=db)
    assert source is None


async def test_relationship_add_remove_related_nodes(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: None
) -> None:
    """Validates that profiles are applied to related nodes when adding/removing related_nodes to a profile."""
    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, name="Alice")
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, name="Bob")
    await person2.save(db=db)

    person1_initial = await NodeManager.get_one(db=db, id=person1.id, branch=default_branch)
    assert person1_initial.height.value is None
    assert person1_initial.height.is_default is True
    assert person1_initial.height.is_from_profile is False

    person2_initial = await NodeManager.get_one(db=db, id=person2.id, branch=default_branch)
    assert person2_initial.height.value is None
    assert person2_initial.height.is_default is True
    assert person2_initial.height.is_from_profile is False

    profile_schema = registry.schema.get("ProfileTestPerson", branch=default_branch)
    profile = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await profile.new(db=db, profile_name="tall-people", profile_priority=100, height=185)
    await profile.save(db=db)

    add_query = """
    mutation RelationshipAdd(
        $id: String!,
        $relationship_name: String!,
        $node_1: String!,
        $node_2: String!,
        ) {
        RelationshipAdd(
            data: {id: $id, name: $relationship_name, nodes: [{id: $node_1}, {id: $node_2}]}
        ) {
        ok
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=add_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": profile.id,
            "relationship_name": "related_nodes",
            "node_1": person1.id,
            "node_2": person2.id,
        },
    )

    assert result.errors is None

    person1_updated = await NodeManager.get_one(
        db=db, id=person1.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert person1_updated.height.value == 185
    assert person1_updated.height.is_default is False
    assert person1_updated.height.is_from_profile is True
    source1 = await person1_updated.height.get_source(db=db)
    assert source1 is not None
    assert source1.id == profile.id

    person2_updated = await NodeManager.get_one(
        db=db, id=person2.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert person2_updated.height.value == 185
    assert person2_updated.height.is_default is False
    assert person2_updated.height.is_from_profile is True
    source2 = await person2_updated.height.get_source(db=db)
    assert source2 is not None
    assert source2.id == profile.id

    remove_query = """
    mutation RelationshipRemove(
        $id: String!,
        $relationship_name: String!,
        $node: String!,
        ) {
        RelationshipRemove(
            data: {id: $id, name: $relationship_name, nodes: [{id: $node}]}
        ) {
        ok
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=remove_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": profile.id, "relationship_name": "related_nodes", "node": person1.id},
    )

    assert result.errors is None

    person1_final = await NodeManager.get_one(
        db=db, id=person1.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert person1_final.height.value is None
    assert person1_final.height.is_default is True
    assert person1_final.height.is_from_profile is False
    source1_final = await person1_final.height.get_source(db=db)
    assert source1_final is None

    person2_final = await NodeManager.get_one(
        db=db, id=person2.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert person2_final.height.value == 185
    assert person2_final.height.is_default is False
    assert person2_final.height.is_from_profile is True
    source2_final = await person2_final.height.get_source(db=db)
    assert source2_final is not None
    assert source2_final.id == profile.id
