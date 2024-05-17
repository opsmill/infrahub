from uuid import uuid4

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_upsert_existing_simple_object_by_id(db: InfrahubDatabase, person_john_main: Node, branch: Branch):
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: { value: "Jim"}}) {
            ok
        }
    }
    """
        % person_john_main.id
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonUpsert"]["ok"] is True

    obj1 = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    assert obj1.name.value == "Jim"
    assert obj1.height.value == 180


async def test_upsert_existing_simple_object_by_default_filter(
    db: InfrahubDatabase, person_john_main: Node, branch: Branch
):
    query = """
    mutation {
        TestPersonUpsert(data: {name: { value: "John"}, height: {value: 138}}) {
            ok
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonUpsert"]["ok"] is True

    obj1 = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    assert obj1.name.value == "John"
    assert obj1.height.value == 138


async def test_upsert_create_simple_object_no_id(db: InfrahubDatabase, person_john_main, branch: Branch):
    query = """
    mutation {
        TestPersonUpsert(data: {name: { value: "%s"}, height: {value: %s}}) {
            ok
            object {
                id
            }
        }
    }
    """ % ("Ellen Ripley", 179)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonUpsert"]["ok"] is True

    person_id = result.data["TestPersonUpsert"]["object"]["id"]
    obj1 = await NodeManager.get_one(db=db, id=person_id, branch=branch)
    assert obj1.name.value == "Ellen Ripley"
    assert obj1.height.value == 179


async def test_upsert_create_simple_object_with_id(db: InfrahubDatabase, person_john_main, branch: Branch):
    fresh_id = str(uuid4())
    query = """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: { value: "%s"}, height: {value: %s}}) {
            ok
            object {
                id
            }
        }
    }
    """ % (fresh_id, "Dwayne Hicks", 168)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonUpsert"]["ok"] is True

    person_id = result.data["TestPersonUpsert"]["object"]["id"]
    assert person_id == fresh_id
    obj1 = await NodeManager.get_one(db=db, id=person_id, branch=branch)
    assert obj1.name.value == "Dwayne Hicks"
    assert obj1.height.value == 168


async def test_cannot_upsert_new_object_without_required_fields(db: InfrahubDatabase, person_john_main, branch: Branch):
    fresh_id = str(uuid4())
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", height: { value: 182}}) {
            ok
        }
    }
    """
        % fresh_id
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    expected_error = "Field 'TestPersonUpsertInput.name' of required type 'TextAttributeUpdate!' was not provided."
    assert any(expected_error in error.message for error in result.errors)

    assert await NodeManager.get_one(db=db, id=fresh_id, branch=branch) is None


async def test_id_for_other_schema_raises_error(
    db: InfrahubDatabase, person_john_main, car_accord_main, branch: Branch
):
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: {value: "John"}, height: { value: 182}}) {
            ok
        }
    }
    """
        % car_accord_main.id
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    expected_error = f"Node with id {car_accord_main.id} exists, but it is a TestCar, not TestPerson"
    assert any(expected_error in error.message for error in result.errors)


async def test_update_by_id_to_nonunique_value_raises_error(
    db: InfrahubDatabase, person_john_main, person_jim_main, branch: Branch
):
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: {value: "Jim"}}) {
            ok
        }
    }
    """
        % person_john_main.id
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    expected_error = "An object already exist with this value: name: Jim at name"
    assert any(expected_error in error.message for error in result.errors)


async def test_with_hfid_existing(db: InfrahubDatabase, default_branch, animal_person_schema):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = (
        """
    mutation {
        TestDogUpsert(data: {
            hfid: ["Jack", "Rocky"],
            name: { value: "Bella" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { id: "%s" }
        }) {
            ok
            object {
                id
                color {
                    value
                }
            }
        }
    }
    """
        % person1.id
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
    assert result.data["TestDogUpsert"]["ok"] is True
    assert result.data["TestDogUpsert"]["object"] == {"color": {"value": "black"}, "id": dog1.id}


async def test_with_hfid_new(db: InfrahubDatabase, default_branch, animal_person_schema):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = (
        """
    mutation {
        TestDogUpsert(data: {
            hfid: ["Jack", "Bella"],
            name: { value: "Bella" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { id: "%s" }
        }) {
            ok
            object {
                id
                name {
                    value
                }
                color {
                    value
                }
                breed {
                    value
                }
            }
        }
    }
    """
        % person1.id
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
    assert result.data["TestDogUpsert"]["ok"] is True
    new_id = result.data["TestDogUpsert"]["object"]["id"]
    assert result.data["TestDogUpsert"]["object"] == {
        "breed": {"value": "Labrador"},
        "color": {"value": "black"},
        "id": new_id,
        "name": {"value": "Bella"},
    }
