from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_create_simple_object(db: InfrahubDatabase, default_branch: Branch, car_person_schema: None) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
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
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPersonCreate"]["ok"] is True

    person_id = result.data["TestPersonCreate"]["object"]["id"]
    assert len(person_id) == 36  # length of an UUID

    person = await NodeManager.get_one(db=db, id=person_id)
    assert person.name.is_default is False
    assert person.height.is_default is False


async def test_create_simple_object_with_ok_return(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: None
) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
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
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    assert result.data["TestPersonCreate"]["ok"] is True


async def test_create_with_id(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    uuid1 = "79c83773-6b23-4537-a3ce-b214b625ff1d"
    query = (
        """
    mutation {
        TestPersonCreate(data: {id: "%s", name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
        % uuid1
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
    assert result.data["TestPersonCreate"]["ok"] is True
    assert result.data["TestPersonCreate"]["object"]["id"] == uuid1

    query = """
    mutation {
        TestPersonCreate(data: {id: "not-valid", name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
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
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "not-valid is not a valid UUID" in result.errors[0].message
