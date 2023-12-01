import pytest
from graphql import graphql

from infrahub.core.node import Node
from infrahub.core.schema import GroupSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql import generate_graphql_schema
from infrahub.graphql.mutations.schema import validate_kind


async def test_delete_last_enum_option(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaEnumRemove(data: {kind: "BaseChoice", attribute: "measuring_system", enum: "metric"}) {
            ok
        }
    }
    """
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "The enum value yellow does not exists on BaseChoice in attribute color" in str(result.errors[0])


async def test_add_enum_option_that_exist(db: InfrahubDatabase, default_branch, choices_schema):
    query = """
    mutation {
        SchemaEnumAdd(data: {kind: "BaseChoice", attribute: "color", enum: "red"}) {
            ok
        }
    }
    """
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "The enum value red already exists on BaseChoice in attribute color" in str(result.errors[0])


async def test_enum_option_in_use(db: InfrahubDatabase, default_branch, choices_schema):
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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "There are still TestChoice objects using this enum" in str(result.errors[0])


async def test_validate_kind_exceptions(db: InfrahubDatabase, choices_schema):
    node = await Node.init(db=db, schema="TestChoice")
    restricted_node = await Node.init(db=db, schema="LineageOwner")
    group_schema = GroupSchema(id="blank", name="dummy", kind="Dummy", description="")

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=group_schema, attribute="status")
    assert "Dummy is not a valid node" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=restricted_node._schema, attribute="status")

    assert "Operation not allowed for LineageOwner in restricted namespace Lineage" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=node._schema, attribute="no_attribute")

    assert "Attribute no_attribute does not exist on TestChoice" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=node._schema, attribute="name")

    assert "Attribute name on TestChoice is not an enum" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_kind(kind=node._schema, attribute="color")

    assert "Attribute color on TestChoice is inherited and must be changed on the generic" in str(exc.value)
