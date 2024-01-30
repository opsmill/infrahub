from uuid import uuid4

import pytest
from graphql import graphql

from infrahub.core.branch.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    expected_error = "Field 'TestPersonCreateInput.name' of required type 'TextAttributeInput!' was not provided."
    assert any([expected_error in error.message for error in result.errors])

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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    expected_error = f"Node with id {car_accord_main.id} exists, but it is a TestCar, not TestPerson"
    assert any([expected_error in error.message for error in result.errors])


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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    expected_error = "An object already exist with this value: name: Jim at name"
    assert any([expected_error in error.message for error in result.errors])
