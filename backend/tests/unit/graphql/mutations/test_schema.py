import pytest
from graphql import graphql

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql import prepare_graphql_params
from infrahub.graphql.mutations.schema import validate_kind, validate_kind_dropdown, validate_kind_enum


async def test_delete_last_dropdown_option(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaDropdownRemove(data: {kind: "TestChoice", attribute: "temperature_scale", dropdown: "celsius"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "Unable to remove the last dropdown on TestChoice in attribute temperature_scale" in str(result.errors[0])


async def test_delete_last_enum_option(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaEnumRemove(data: {kind: "BaseChoice", attribute: "measuring_system", enum: "metric"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "Unable to remove the last enum on BaseChoice in attribute measuring_system" in str(result.errors[0])


async def test_delete_enum_option_that_does_not_exist(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaEnumRemove(data: {kind: "BaseChoice", attribute: "color", enum: "yellow"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "The enum value yellow does not exists on BaseChoice in attribute color" in str(result.errors[0])


async def test_delete_drop_option_that_does_not_exist(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaDropdownRemove(data: {kind: "BaseChoice", attribute: "section", dropdown: "ci"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "The dropdown value ci does not exists on BaseChoice in attribute section" in str(result.errors[0])


async def test_add_enum_option_that_exist(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaEnumAdd(data: {kind: "BaseChoice", attribute: "color", enum: "red"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "The enum value red already exists on BaseChoice in attribute color" in str(result.errors[0])


async def test_delete_dropdown_option_in_use(db: InfrahubDatabase, default_branch, choices_schema):
    obj1 = await Node.init(db=db, schema="TestChoice")
    await obj1.new(db=db, name="test-passive-01", status="passive", temperature_scale="celsius")
    await obj1.save(db=db)

    query = """
    mutation {
        SchemaDropdownRemove(data: {kind: "TestChoice", attribute: "temperature_scale", dropdown: "celsius"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "There are still TestChoice objects using this dropdown" in str(result.errors[0])


async def test_delete_enum_option_in_use(db: InfrahubDatabase, default_branch, choices_schema):
    obj1 = await Node.init(db=db, schema="TestChoice")
    await obj1.new(db=db, name="test-passive-01", status="passive")
    await obj1.save(db=db)

    query = """
    mutation {
        SchemaEnumRemove(data: {kind: "TestChoice", attribute: "status", enum: "passive"}) {
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
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "There are still TestChoice objects using this enum" in str(result.errors[0])


async def test_validate_kind_exceptions(db: InfrahubDatabase, choices_schema):
    node = await Node.init(db=db, schema="TestChoice")
    restricted_node = await Node.init(db=db, schema="LineageOwner")

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=restricted_node._schema, attribute="status")

    assert "Operation not allowed for LineageOwner in restricted namespace Lineage" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=node._schema, attribute="no_attribute")

    assert "Attribute no_attribute does not exist on TestChoice" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=node._schema, attribute="color")

    assert "Attribute color on TestChoice is inherited and must be changed on the generic" in str(exc.value)


async def test_validate_kind_dropdown_exceptions(db: InfrahubDatabase, choices_schema):
    node = await Node.init(db=db, schema="TestChoice")

    with pytest.raises(ValidationError) as exc:
        validate_kind_dropdown(kind=node._schema, attribute="comment")

    assert "Attribute comment on TestChoice is not a Dropdown" in str(exc.value)


async def test_validate_kind_enum_exceptions(db: InfrahubDatabase, choices_schema):
    node = await Node.init(db=db, schema="TestChoice")

    with pytest.raises(ValidationError) as exc:
        validate_kind_enum(kind=node._schema, attribute="comment")

    assert "Attribute comment on TestChoice is not an enum" in str(exc.value)
