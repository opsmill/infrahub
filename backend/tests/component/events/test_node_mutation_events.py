from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipPeerChangelog,
)
from infrahub.core.constants import DiffAction, InfrahubKind, MutationAction
from infrahub.core.manager import NodeManager
from infrahub.core.mutation_context import RecordedNode
from infrahub.core.node import Node
from infrahub.events.generator import generate_node_mutation_events
from infrahub.events.group_action import GroupMemberAddedEvent
from infrahub.events.models import EventBranchContext, EventContext, EventNode, InfrahubEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeUpdatedEvent

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def _generate_events(
    db: InfrahubDatabase,
    branch: Branch,
    node: Node,
    action: MutationAction,
    recorded_nodes: list[RecordedNode],
) -> list[InfrahubEvent]:
    return await generate_node_mutation_events(
        node=node,
        deleted_nodes=[],
        db=db,
        branch=branch,
        context=EventContext(branch=EventBranchContext(name=branch.name), account_id="test-account"),
        request_id="test-request",
        action=action,
        recorded_nodes=recorded_nodes,
    )


async def test_an_updated_node_keeps_the_update_derived_from_its_new_relationship_to_the_main_node(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """An updated node's own event lacks the relationship the main node added, so both of its updates are sent."""
    first_owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await first_owner.new(db=db, name="Jack")
    await first_owner.save(db=db)
    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=first_owner)
    await dog.save(db=db)
    weighed_dog = await NodeManager.get_one(db=db, id=dog.id, branch=default_branch, raise_on_error=True)
    weighed_dog.get_attribute("weight").value = 12
    await weighed_dog.save(db=db)
    new_owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_owner.new(db=db, name="Jane", animals=[weighed_dog])
    await new_owner.save(db=db)

    events = await _generate_events(
        db=db,
        branch=default_branch,
        node=new_owner,
        action=MutationAction.CREATED,
        recorded_nodes=[RecordedNode(node=weighed_dog, action=MutationAction.UPDATED)],
    )

    dog_updates = [
        sorted(event.fields) for event in events if isinstance(event, NodeUpdatedEvent) and event.node_id == dog.id
    ]
    assert sorted(dog_updates) == [["owner"], ["weight"]]


async def test_a_created_node_saved_before_its_link_keeps_the_update_derived_from_that_link(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A node saved before the main node links to it, as a pool allocation is, has a created event without that link."""
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)

    events = await _generate_events(
        db=db,
        branch=default_branch,
        node=dog,
        action=MutationAction.CREATED,
        recorded_nodes=[RecordedNode(node=owner, action=MutationAction.CREATED)],
    )

    owner_events = [
        (type(event), sorted(event.fields))
        for event in events
        if isinstance(event, NodeCreatedEvent | NodeUpdatedEvent) and event.node_id == owner.id
    ]
    assert sorted(owner_events, key=lambda owner_event: owner_event[0].__name__) == [
        (NodeCreatedEvent, ["display_label", "height", "human_friendly_id", "name"]),
        (NodeUpdatedEvent, ["animals"]),
    ]


async def test_a_created_group_holding_the_main_node_sends_a_member_added_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    animal_person_schema: SchemaBranch,
) -> None:
    member = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await member.new(db=db, name="Jack")
    await member.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await group.new(db=db, name="team", members=[member])
    await group.save(db=db)

    events = await _generate_events(
        db=db,
        branch=default_branch,
        node=member,
        action=MutationAction.CREATED,
        recorded_nodes=[RecordedNode(node=group, action=MutationAction.CREATED)],
    )

    member_added = [(event.node_id, event.members) for event in events if isinstance(event, GroupMemberAddedEvent)]
    assert member_added == [(group.id, [EventNode(id=member.id, kind="TestPerson")])]


async def test_a_main_node_joining_a_created_group_sends_one_member_added_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    animal_person_schema: SchemaBranch,
) -> None:
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await group.new(db=db, name="team")
    await group.save(db=db)
    member = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await member.new(db=db, name="Jack", member_of_groups=[group])
    await member.save(db=db)

    events = await _generate_events(
        db=db,
        branch=default_branch,
        node=member,
        action=MutationAction.CREATED,
        recorded_nodes=[RecordedNode(node=group, action=MutationAction.CREATED)],
    )

    member_added = [(event.node_id, event.members) for event in events if isinstance(event, GroupMemberAddedEvent)]
    assert member_added == [(group.id, [EventNode(id=member.id, kind="TestPerson")])]


def _recorded_changelog(node: Node, relationship: str, peer: Node, status: DiffAction) -> NodeChangelog:
    """Build the change log a recorded node's own save would hold for one change to one of its relationships."""
    return NodeChangelog(
        node_id=node.get_id(),
        node_kind=node.get_kind(),
        display_label="n/a",
        relationships={
            relationship: RelationshipCardinalityManyChangelog(
                name=relationship,
                peers=[RelationshipPeerChangelog(peer_id=peer.get_id(), peer_kind=peer.get_kind(), peer_status=status)],
            )
        },
    )


async def test_a_recorded_node_removing_the_main_node_keeps_the_update_adding_it(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """The recorded node's own event names the main node as a removed peer, so it does not report the added link."""
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)
    owner._node_changelog = _recorded_changelog(node=owner, relationship="animals", peer=dog, status=DiffAction.REMOVED)

    events = await _generate_events(
        db=db,
        branch=default_branch,
        node=dog,
        action=MutationAction.CREATED,
        recorded_nodes=[RecordedNode(node=owner, action=MutationAction.CREATED)],
    )

    owner_updates = [
        sorted(event.fields) for event in events if isinstance(event, NodeUpdatedEvent) and event.node_id == owner.id
    ]
    assert owner_updates == [["animals"]]


async def test_an_updated_group_already_holding_the_main_node_sends_one_member_added_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    animal_person_schema: SchemaBranch,
) -> None:
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await group.new(db=db, name="team")
    await group.save(db=db)
    member = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await member.new(db=db, name="Jack", member_of_groups=[group])
    await member.save(db=db)
    group._node_changelog = _recorded_changelog(
        node=group, relationship="members", peer=member, status=DiffAction.ADDED
    )

    events = await _generate_events(
        db=db,
        branch=default_branch,
        node=member,
        action=MutationAction.CREATED,
        recorded_nodes=[RecordedNode(node=group, action=MutationAction.UPDATED)],
    )

    member_added = [(event.node_id, event.members) for event in events if isinstance(event, GroupMemberAddedEvent)]
    assert member_added == [(group.id, [EventNode(id=member.id, kind="TestPerson")])]
