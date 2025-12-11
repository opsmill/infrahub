import pytest

from infrahub.auth import AccountSession
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.schema import validate_kind, validate_kind_dropdown, validate_kind_enum
from infrahub.services import InfrahubServices
from infrahub.services.component import InfrahubComponent
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql


async def test_delete_last_dropdown_option(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
    query = """
    mutation {
        SchemaDropdownRemove(data: {kind: "TestChoice", attribute: "temperature_scale", dropdown: "celsius"}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_delete_last_enum_option(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
    query = """
    mutation {
        SchemaEnumRemove(data: {kind: "BaseChoice", attribute: "measuring_system", enum: "metric"}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_delete_enum_option_that_does_not_exist(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
    query = """
    mutation {
        SchemaEnumRemove(data: {kind: "BaseChoice", attribute: "color", enum: "yellow"}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_delete_drop_option_that_does_not_exist(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
    query = """
    mutation {
        SchemaDropdownRemove(data: {kind: "BaseChoice", attribute: "section", dropdown: "ci"}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_add_enum_option_that_exist(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
    query = """
    mutation {
        SchemaEnumAdd(data: {kind: "BaseChoice", attribute: "color", enum: "red"}) {
            ok
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_delete_dropdown_option_in_use(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_delete_enum_option_in_use(
    db: InfrahubDatabase, default_permission_backend, default_branch: Branch, choices_schema, session_admin
) -> None:
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)
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


async def test_validate_kind_exceptions(db: InfrahubDatabase, choices_schema) -> None:
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


async def test_validate_kind_dropdown_exceptions(db: InfrahubDatabase, choices_schema) -> None:
    node = await Node.init(db=db, schema="TestChoice")

    with pytest.raises(ValidationError) as exc:
        validate_kind_dropdown(kind=node._schema, attribute="comment")

    assert "Attribute comment on TestChoice is not a Dropdown" in str(exc.value)


async def test_validate_kind_enum_exceptions(db: InfrahubDatabase, choices_schema) -> None:
    node = await Node.init(db=db, schema="TestChoice")

    with pytest.raises(ValidationError) as exc:
        validate_kind_enum(kind=node._schema, attribute="comment")

    assert "Attribute comment on TestChoice is not an enum" in str(exc.value)


async def test_add_dropdown_option_does_not_corrupt_schema_cache(
    db: InfrahubDatabase,
    default_permission_backend: None,
    default_branch: Branch,
    choices_schema: None,
    session_admin: AccountSession,
) -> None:
    """Test that adding a dropdown option does not corrupt the schema cache.

    This test reproduces issue #7780 where adding a dropdown option via the UI
    would modify the cached schema object directly, causing hash mismatches when
    other code paths tried to retrieve the schema.

    The bug occurs when:
    1. Schema is fetched with duplicate=False (returns cached object)
    2. The cached object is mutated (e.g., adding a dropdown option)
    3. The mutated object's hash changes, but old hash key remains in cache (stale)
    4. When purge_inactive_branches runs, it computes hashes to keep using get_hash()
       which returns the NEW hash, so the OLD hash entry gets deleted
    5. Any code with a reference to a SchemaBranch using the old hash fails
    """
    cache = MemoryCache()
    bus = BusRecorder()
    service = await InfrahubServices.new(
        database=db,
        message_bus=bus,
        cache=cache,
        component_type=ComponentType.API_SERVER,
        component=InfrahubComponent(cache=cache, db=db, message_bus=bus, component_type=ComponentType.API_SERVER),
    )

    # Get the schema branch BEFORE the mutation - this simulates another process
    # that cached the schema branch (e.g., another API request in flight).
    # We use duplicate() to get a separate SchemaBranch instance that shares the cache.
    schema_before = registry.schema.get_schema_branch(name=default_branch.name).duplicate()

    # Verify the schema is retrievable with the original hash
    test_choice_schema = schema_before.get(name="TestChoice", duplicate=False)
    assert test_choice_schema is not None

    # Get the original choices BEFORE mutation
    original_temp_attr = test_choice_schema.get_attribute("temperature_scale")
    assert original_temp_attr.choices
    original_choices = [c.name for c in original_temp_attr.choices]
    assert original_choices == ["celsius"]

    query = """
    mutation {
        SchemaDropdownAdd(data: {kind: "TestChoice", attribute: "temperature_scale", dropdown: "fahrenheit"}) {
            ok
            object {
                value
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, account_session=session_admin, service=service
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    assert result.data["SchemaDropdownAdd"]["ok"] is True
    assert result.data["SchemaDropdownAdd"]["object"]["value"] == "fahrenheit"

    # Verify that the new dropdown was actually saved by checking the registry
    schema_after = registry.schema.get_schema_branch(name=default_branch.name)
    test_choice_after = schema_after.get(name="TestChoice", duplicate=False)
    temp_attr_after = test_choice_after.get_attribute("temperature_scale")
    assert temp_attr_after.choices
    choices_after = [c.name for c in temp_attr_after.choices]
    assert "fahrenheit" in choices_after, f"Dropdown 'fahrenheit' not found in choices: {choices_after}"
    assert "celsius" in choices_after

    # The bug: The mutation modified the cached schema object in-place (with duplicate=False),
    # so test_choice_schema (which we got before the mutation) now has the new dropdown too.
    # This proves the cached object was mutated rather than a copy being modified.
    mutated_temp_attr = test_choice_schema.get_attribute("temperature_scale")
    assert mutated_temp_attr.choices
    mutated_choices = [c.name for c in mutated_temp_attr.choices]

    # If the fix is NOT in place, the original object was mutated:
    # mutated_choices will contain "fahrenheit" even though we got it before the mutation
    if "fahrenheit" in mutated_choices:
        pytest.fail(
            f"Bug #7780: Cached schema object was mutated in-place. "
            f"Original object now has choices {mutated_choices} instead of ['celsius']"
        )
