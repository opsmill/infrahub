from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"person_id": person1.id},
    )

    assert result.errors is None
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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
