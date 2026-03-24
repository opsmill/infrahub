import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m056_update_schema_node_generic_constraints import Migration056
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.definitions.internal import (
    attribute_schema,
    relationship_schema,
)
from infrahub.core.schema.definitions.internal import (
    generic_schema as internal_generic_schema,
)
from infrahub.core.schema.definitions.internal import (
    node_schema as internal_node_schema,
)
from infrahub.core.schema.manager import SchemaManager
from infrahub.database import InfrahubDatabase


async def _validate_schema_state(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    expect_old_values: bool,
) -> None:
    """Helper to validate the schema state on a given branch.

    Args:
        db: Database connection
        branch: Branch to check
        expect_old_values: If True, expect old values (pre-migration), if False expect new values (post-migration)
    """
    schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
    schema_node = schema_branch.get_node(name="SchemaNode", duplicate=False)
    schema_generic = schema_branch.get_node(name="SchemaGeneric", duplicate=False)

    if expect_old_values:
        # Validate old/pre-migration state
        assert schema_node.get_attribute("name").unique is True
        assert schema_node.uniqueness_constraints == [["name__value"]]
        assert schema_node.human_friendly_id == ["name__value"]

        assert schema_generic.get_attribute("name").unique is True
        assert schema_generic.uniqueness_constraints == [["name__value"]]
        assert schema_generic.human_friendly_id == ["name__value"]
    else:
        # Validate new/post-migration state
        assert schema_node.get_attribute("name").unique is False
        assert schema_node.uniqueness_constraints == [["namespace__value", "name__value"]]
        assert schema_node.human_friendly_id == ["namespace__value", "name__value"]

        assert schema_generic.get_attribute("name").unique is False
        assert schema_generic.uniqueness_constraints == [["namespace__value", "name__value"]]
        assert schema_generic.human_friendly_id == ["namespace__value", "name__value"]


@pytest.fixture
async def migration_056_data(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
) -> None:
    """Set up the database with old versions of SchemaNode and SchemaGeneric."""
    # Create copies of the internal schema definitions with old values
    old_node_schema = internal_node_schema.model_copy(deep=True)
    old_node_schema.uniqueness_constraints = [["name__value"]]
    old_node_schema.human_friendly_id = ["name__value"]
    # Set name attribute to unique = True
    for attr in old_node_schema.attributes:
        if attr.name == "name":
            attr.unique = True
            break

    old_generic_schema = internal_generic_schema.model_copy(deep=True)
    old_generic_schema.uniqueness_constraints = [["name__value"]]
    old_generic_schema.human_friendly_id = ["name__value"]
    # Set name attribute to unique = True
    for attr in old_generic_schema.attributes:
        if attr.name == "name":
            attr.unique = True
            break

    # Create a schema root with SchemaNode, SchemaGeneric, and their dependencies
    # Include SchemaAttribute and SchemaRelationship since SchemaNode/Generic have relationships to them
    schema_dict = {
        "version": internal_schema["version"],
        "nodes": [
            attribute_schema.to_dict(),
            relationship_schema.to_dict(),
            old_node_schema.to_dict(),
            old_generic_schema.to_dict(),
        ],
    }
    schema_root = SchemaRoot(**schema_dict)

    # Initialize schema manager and register the schema
    manager = SchemaManager()
    registry.schema = manager
    schema_branch = manager.register_schema(schema=schema_root, branch=default_branch.name)
    default_branch.update_schema_hash()

    # Load all schemas to the database (SchemaNode, SchemaGeneric, and their dependencies)
    await manager.load_schema_to_db(
        schema=schema_branch,
        db=db,
        branch=default_branch,
    )


async def test_migration_056(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    migration_056_data: None,
) -> None:
    """Test migration 056: updates SchemaNode and SchemaGeneric constraints on all branches."""
    # Create a user branch before running the migration
    user_branch = await create_branch(db=db, branch_name="test-migration-056")

    # Verify initial state (old values) on both branches
    await _validate_schema_state(db, default_branch, expect_old_values=True)
    await _validate_schema_state(db, user_branch, expect_old_values=True)

    # Execute the migration
    migration = Migration056()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    # Verify the updated state (new values) on both branches
    await _validate_schema_state(db, default_branch, expect_old_values=False)
    await _validate_schema_state(db, user_branch, expect_old_values=False)

    # Test idempotency: run migration again
    execution_result_2 = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result_2.errors

    # Verify the state is still correct after second execution
    await _validate_schema_state(db, default_branch, expect_old_values=False)
    await _validate_schema_state(db, user_branch, expect_old_values=False)
