from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m068_cleanup_branch_schema_parameters import (
    ALL_NULL_PARAMETER_VALUES,
    Migration068,
)
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
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def _get_schema_attr_ids(manager: SchemaManager, branch_name: str, kind: str) -> dict[str, str]:
    """Get a map of attribute name -> attribute id for a specific schema kind."""
    schema_branch = manager.get_schema_branch(name=branch_name)
    node_schema = schema_branch.get_node(name=kind, duplicate=False)
    return {attr.name: attr.id for attr in node_schema.attributes if attr.id}


def _get_node_attr_ids(manager: SchemaManager, branch_name: str) -> dict[str, str]:
    return _get_schema_attr_ids(manager, branch_name, "SchemaNode")


def _get_generic_attr_ids(manager: SchemaManager, branch_name: str) -> dict[str, str]:
    return _get_schema_attr_ids(manager, branch_name, "SchemaGeneric")


async def _get_raw_parameter(db: InfrahubDatabase, attr_id: str, branch: Branch) -> str | None:
    """Get the raw DB parameters value for a SchemaAttribute on a branch."""
    results = await db.execute_query(
        query="""
        MATCH (n {uuid: $attr_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "parameters"})-[hv:HAS_VALUE]->(av:AttributeValue)
        WHERE hv.branch = $branch_name AND hv.status = "active" AND hv.to IS NULL
        RETURN av.value AS param_value
        """,
        params={"attr_id": attr_id, "branch_name": branch.name},
        name="get_raw_parameter",
    )
    if not results:
        return None
    return results[0].get("param_value")


async def _set_raw_parameter(db: InfrahubDatabase, attr_id: str, branch: Branch, value: str) -> None:
    """Set the raw DB parameters value for a SchemaAttribute on a branch."""
    at = Timestamp().to_string()
    await db.execute_query(
        query="""
        MATCH (n {uuid: $attr_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "parameters"})
        MERGE (av:AttributeValue {value: $value, is_default: false})
        CREATE (a)-[:HAS_VALUE {
            branch: $branch_name,
            branch_level: $branch_level,
            status: "active",
            from: $at
        }]->(av)
        """,
        params={
            "attr_id": attr_id,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "value": value,
            "at": at,
        },
        name="set_raw_parameter",
    )


@pytest.fixture
async def schema_data(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
) -> SchemaManager:
    """Set up SchemaNode and SchemaGeneric in the database and return the manager."""
    schema_dict = {
        "version": internal_schema["version"],
        "nodes": [
            attribute_schema.to_dict(),
            relationship_schema.to_dict(),
            internal_node_schema.to_dict(),
            internal_generic_schema.to_dict(),
        ],
    }
    schema_root = SchemaRoot(**schema_dict)

    manager = SchemaManager()
    registry.schema = manager
    schema_branch = manager.register_schema(schema=schema_root, branch=default_branch.name)
    default_branch.update_schema_hash()

    await manager.load_schema_to_db(
        schema=schema_branch,
        db=db,
        branch=default_branch,
    )

    # Reset parameters to "NULL" on the default branch to simulate pre-M056 state
    for attr_id in _get_node_attr_ids(manager, default_branch.name).values():
        await _set_raw_parameter(db=db, attr_id=attr_id, branch=default_branch, value="NULL")
    for attr_id in _get_generic_attr_ids(manager, default_branch.name).values():
        await _set_raw_parameter(db=db, attr_id=attr_id, branch=default_branch, value="NULL")

    return manager


async def test_migration_068(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    schema_data: SchemaManager,
) -> None:
    """Test that Migration068 fixes spurious branch parameters written by the old Migration056.

    Sets up three scenarios:
    1. Branch with all-null JSON parameters (Text-style) -> should be fixed
    2. Branch with all-null JSON parameters (bare style) -> should be fixed
    3. Branch with legitimate (non-null) parameters -> should NOT be touched
    """
    node_attrs = _get_node_attr_ids(schema_data, default_branch.name)
    generic_attrs = _get_generic_attr_ids(schema_data, default_branch.name)

    # Create branches
    branch_text = await create_branch(db=db, branch_name="fix-text-params")
    branch_bare = await create_branch(db=db, branch_name="fix-bare-params")
    branch_legit = await create_branch(db=db, branch_name="legit-params")

    # Scenario 1: Text-style all-null parameters on SchemaNode attrs
    text_null_value = '{"id":null,"state":"present","regex":null,"min_length":null,"max_length":null}'
    for attr_name in ["name", "namespace", "description"]:
        await _set_raw_parameter(db=db, attr_id=node_attrs[attr_name], branch=branch_text, value=text_null_value)

    # Scenario 2: Bare-style all-null parameters on SchemaGeneric attrs
    bare_null_value = '{"id":null,"state":"present"}'
    for attr_name in ["name", "namespace"]:
        await _set_raw_parameter(db=db, attr_id=generic_attrs[attr_name], branch=branch_bare, value=bare_null_value)

    # Scenario 3: Legitimate non-null parameters on SchemaNode attr
    legit_value = '{"id":null,"state":"present","regex":"^[A-Z]","min_length":1,"max_length":100}'
    await _set_raw_parameter(db=db, attr_id=node_attrs["name"], branch=branch_legit, value=legit_value)

    # Verify injected data
    assert await _get_raw_parameter(db, node_attrs["name"], branch_text) == text_null_value
    assert await _get_raw_parameter(db, node_attrs["namespace"], branch_text) == text_null_value
    assert await _get_raw_parameter(db, node_attrs["description"], branch_text) == text_null_value
    assert await _get_raw_parameter(db, generic_attrs["name"], branch_bare) == bare_null_value
    assert await _get_raw_parameter(db, generic_attrs["namespace"], branch_bare) == bare_null_value
    assert await _get_raw_parameter(db, node_attrs["name"], branch_legit) == legit_value

    # Run the migration
    migration = Migration068()
    result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not result.errors

    # Verify: SchemaNode spurious parameters restored to "NULL"
    assert await _get_raw_parameter(db, node_attrs["name"], branch_text) == "NULL"
    assert await _get_raw_parameter(db, node_attrs["namespace"], branch_text) == "NULL"
    assert await _get_raw_parameter(db, node_attrs["description"], branch_text) == "NULL"

    # Verify: SchemaGeneric spurious parameters restored to "NULL"
    assert await _get_raw_parameter(db, generic_attrs["name"], branch_bare) == "NULL"
    assert await _get_raw_parameter(db, generic_attrs["namespace"], branch_bare) == "NULL"

    # Verify: legitimate parameter untouched
    assert await _get_raw_parameter(db, node_attrs["name"], branch_legit) == legit_value

    # Run again for idempotency
    result_2 = await migration.execute(migration_input=MigrationInput(db=db))
    assert not result_2.errors

    # Verify: unchanged after second run
    assert await _get_raw_parameter(db, node_attrs["name"], branch_text) == "NULL"
    assert await _get_raw_parameter(db, node_attrs["namespace"], branch_text) == "NULL"
    assert await _get_raw_parameter(db, node_attrs["description"], branch_text) == "NULL"
    assert await _get_raw_parameter(db, generic_attrs["name"], branch_bare) == "NULL"
    assert await _get_raw_parameter(db, generic_attrs["namespace"], branch_bare) == "NULL"
    assert await _get_raw_parameter(db, node_attrs["name"], branch_legit) == legit_value


async def test_migration_068_no_branch_parameters(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    schema_data: SchemaManager,
) -> None:
    """Migration should complete cleanly when no branches have spurious parameters."""
    await create_branch(db=db, branch_name="clean-branch")

    migration = Migration068()
    result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not result.errors


async def test_migration_068_skips_merged_branches(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    schema_data: SchemaManager,
) -> None:
    """Migration should skip merged branches even if they have spurious parameters."""
    from infrahub.core.branch.enums import BranchStatus

    node_attrs = _get_node_attr_ids(schema_data, default_branch.name)
    merged_branch = await create_branch(db=db, branch_name="merged-branch")

    await _set_raw_parameter(
        db=db, attr_id=node_attrs["name"], branch=merged_branch, value=ALL_NULL_PARAMETER_VALUES[0]
    )

    merged_branch.status = BranchStatus.MERGED
    await merged_branch.save(db=db)

    migration = Migration068()
    result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not result.errors

    assert await _get_raw_parameter(db, node_attrs["name"], merged_branch) == ALL_NULL_PARAMETER_VALUES[0]
