from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.group_action import GroupMemberAddedEvent, GroupMemberRemovedEvent
from infrahub.events.models import EventNode
from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql


async def test_node_mutation_to_group_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    standard_group_schema: None,
    session_first_account: AccountSession,
) -> None:
    root_group = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await root_group.new(db=db, name="root_group")
    await root_group.save(db=db)
    parent_group = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await parent_group.new(db=db, name="parent_group", parent=root_group)
    await parent_group.save(db=db)
    child_group_1 = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await child_group_1.new(db=db, name="child_group_1", parent=parent_group)
    await child_group_1.save(db=db)
    orphan_group_1 = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await orphan_group_1.new(db=db, name="orphan_group_1")
    await orphan_group_1.save(db=db)

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )

    create_query = """
    mutation($group: String) {
        TestPersonCreate(data:
            {
                name: { value: "John"},
                member_of_groups: [{id: $group}]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=create_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"group": child_group_1.id},
    )

    assert not result.errors
    assert result.data
    person_id = result.data["TestPersonCreate"]["object"]["id"]

    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 3
    person_created = memory_event.events[0]
    group_updated = memory_event.events[1]
    member_added = memory_event.events[2]
    assert isinstance(person_created, NodeCreatedEvent)
    assert isinstance(group_updated, NodeUpdatedEvent)
    assert isinstance(member_added, GroupMemberAddedEvent)
    assert person_created.node_id == person_id
    assert group_updated.node_id == child_group_1.get_id()
    assert member_added.node_id == child_group_1.get_id()
    assert len(member_added.members) == 1
    assert EventNode(id=person_id, kind="TestPerson") in member_added.members
    assert len(member_added.ancestors) == 2
    assert EventNode(id=parent_group.id, kind="CoreStandardGroup") in member_added.ancestors
    assert EventNode(id=root_group.id, kind="CoreStandardGroup") in member_added.ancestors

    update_query = """
    mutation($group1: String, $group2: String, $id: String!) {
        TestPersonUpdate(data:
            {
                id: $id,
                member_of_groups: [{id: $group1}, {id: $group2}]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=update_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"group1": child_group_1.id, "group2": orphan_group_1.id, "id": person_id},
    )
    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

    # As the TestPerson already was a member of child_group_1 we don't expect to see any group
    # events for that group
    assert len(memory_event.events) == 3
    person_updated = memory_event.events[0]
    group_updated = memory_event.events[1]
    member_added = memory_event.events[2]
    assert isinstance(person_updated, NodeUpdatedEvent)
    assert isinstance(group_updated, NodeUpdatedEvent)
    assert isinstance(member_added, GroupMemberAddedEvent)
    assert person_updated.node_id == person_id
    assert group_updated.node_id == orphan_group_1.get_id()
    assert member_added.node_id == orphan_group_1.get_id()
    assert len(member_added.members) == 1
    assert EventNode(id=person_id, kind="TestPerson") in member_added.members
    assert len(member_added.ancestors) == 0

    delete_query = """
    mutation( $id: String!) {
        TestPersonDelete(data:
            {
                id: $id,
            }
        ) {
            ok
        }
    }
    """
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=delete_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": person_id},
    )
    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 5
    person_deleted = memory_event.events[0]
    groups_updated = memory_event.events[1:3]
    members_removed = memory_event.events[3:5]
    assert isinstance(person_deleted, NodeDeletedEvent)
    assert len(groups_updated) == 2
    assert isinstance(groups_updated[0], NodeUpdatedEvent)
    assert isinstance(groups_updated[1], NodeUpdatedEvent)
    assert len(members_removed) == 2
    assert isinstance(members_removed[0], GroupMemberRemovedEvent)
    assert isinstance(members_removed[1], GroupMemberRemovedEvent)
    assert person_deleted.node_id == person_id
    removal_events: list[GroupMemberRemovedEvent] = [members_removed[0], members_removed[1]]
    child_group_event = [event for event in removal_events if event.node_id == child_group_1.id][0]
    orphan_group_event = [event for event in removal_events if event.node_id == orphan_group_1.id][0]
    assert len(child_group_event.members) == 1
    assert EventNode(id=person_id, kind="TestPerson") in child_group_event.members
    assert len(child_group_event.ancestors) == 2
    assert EventNode(id=parent_group.id, kind="CoreStandardGroup") in child_group_event.ancestors
    assert EventNode(id=root_group.id, kind="CoreStandardGroup") in child_group_event.ancestors
    assert len(orphan_group_event.members) == 1
    assert EventNode(id=person_id, kind="TestPerson") in orphan_group_event.members
    assert len(orphan_group_event.ancestors) == 0
