from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import MutationAction, RelationshipDeleteBehavior
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.models import ParentEvent
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql


async def test_delete_object(db: InfrahubDatabase, default_branch, car_person_schema):
    obj1 = await Node.init(db=db, schema="TestPerson")
    await obj1.new(db=db, name="John", height=180)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema="TestPerson")
    await obj2.new(db=db, name="Jim", height=160)
    await obj2.save(db=db)
    obj3 = await Node.init(db=db, schema="TestPerson")
    await obj3.new(db=db, name="Joe", height=170)
    await obj3.save(db=db)

    query = (
        """
    mutation {
        TestPersonDelete(data: {id: "%s"}) {
            ok
        }
    }
    """
        % obj1.id
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
    assert result.data
    assert result.data["TestPersonDelete"]["ok"] is True

    assert not await NodeManager.get_one(db=db, id=obj1.id)


async def test_delete_prevented(
    db: InfrahubDatabase, default_branch, car_person_schema, car_camry_main, person_jane_main
):
    query = (
        """
    mutation {
        TestPersonDelete(data: {id: "%s"}) {
            ok
        }
    }
    """
        % person_jane_main.id
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
    assert len(result.errors) == 1
    assert f"Cannot delete TestPerson '{person_jane_main.id}'." in result.errors[0].message
    assert (
        f"It is linked to mandatory relationship owner on node TestCar '{car_camry_main.id}'"
        in result.errors[0].message
    )
    assert result.data
    assert result.data["TestPersonDelete"] is None

    assert await NodeManager.get_one(db=db, id=person_jane_main.id) is not None


async def test_delete_allowed_when_peer_rel_optional_on_generic(
    db: InfrahubDatabase, default_branch, animal_person_schema
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)
    person2 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person2.new(db=db, name="Jill")
    await person2.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person2, best_friend=person1)
    await dog1.save(db=db)

    query = """
    mutation DeletePerson($person_id: String!){
        TestPersonDelete(data: {id: $person_id}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"person_id": person1.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPersonDelete"]["ok"] is True

    updated_dog1 = await NodeManager.get_one(db=db, id=dog1.id)
    updated_best_friend = await updated_dog1.best_friend.get_peer(db=db)
    assert updated_best_friend is None


async def test_delete_prevented_when_peer_rel_required_on_generic(
    db: InfrahubDatabase, default_branch, animal_person_schema
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = """
    mutation DeletePerson($person_id: String!){
        TestPersonDelete(data: {id: $person_id}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"person_id": person1.id},
    )

    expected_error_message = f"Cannot delete TestPerson '{person1.id}'."
    expected_error_message += f" It is linked to mandatory relationship owner on node TestDog '{dog1.id}'"
    assert result.errors
    assert len(result.errors) == 1
    assert expected_error_message in result.errors[0].message


async def test_delete_events_with_cascade(
    db,
    default_branch: Branch,
    dependent_generics_schema: SchemaBranch,
    enable_broker_config: None,
    session_first_account: AccountSession,
) -> None:
    # set TestPerson.animals to be cascade delete
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    for schema_kind in ("TestPerson", "TestHuman", "TestCylon"):
        schema = schema_branch.get(name=schema_kind, duplicate=False)
        schema.get_relationship("animals").on_delete = RelationshipDeleteBehavior.CASCADE

    human = await Node.init(db=db, schema="TestHuman", branch=default_branch)
    await human.new(db=db, name="Jane", height=180)
    await human.save(db=db)
    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Roofus", breed="whocares", weight=50, owner=human)
    await dog.save(db=db)

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    query = """
    mutation DeletePerson($human_id: String!){
        TestHumanDelete(data: {id: $human_id}) {
            ok
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"human_id": human.id},
    )

    assert not result.errors

    node_map = await NodeManager.get_many(db=db, ids=[human.id, dog.id])
    assert node_map == {}

    assert gql_params.context.background
    await gql_params.context.background()
    assert len(memory_event.events) == 2
    primary = memory_event.events[0]
    secondary = memory_event.events[1]
    assert isinstance(primary, NodeMutatedEvent)
    assert isinstance(secondary, NodeMutatedEvent)
    assert primary.kind == "TestHuman"
    assert primary.node_id == human.id
    assert primary.action == MutationAction.DELETED
    assert primary.meta.has_children

    assert secondary.kind == "TestDog"
    assert secondary.node_id == dog.id
    assert secondary.action == MutationAction.DELETED
    assert not secondary.meta.has_children
    assert secondary.meta.parent == primary.meta.id
    assert secondary.meta.ancestors == [ParentEvent(id=primary.get_id(), name=primary.event_name)]
