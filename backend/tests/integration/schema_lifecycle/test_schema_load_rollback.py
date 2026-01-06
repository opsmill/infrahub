"""Integration tests for schema load rollback functionality.

When a schema migration fails, the database changes and registry should be
rolled back to their original state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator, Sequence

import httpx
import pytest

import infrahub.core.migrations.schema.tasks as tasks_module
from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationInput, MigrationResult, SchemaMigration
from infrahub.core.node import Node

from ..shared import load_schema
from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    PERSON_KIND,
    TAG_KIND,
    TestSchemaLifecycleBase,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query import MigrationBaseQuery
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class BrokenMigration(SchemaMigration):
    """A migration class that always fails."""

    name: str = "broken_migration"
    queries: list = []  # Required field, but we won't use it since we override execute

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        """Raise an error to simulate a migration failure."""
        raise ValueError("Simulated migration failure - this is intentional for testing")


@pytest.fixture
def patched_migrations() -> Generator[None, None, None]:
    original_map = tasks_module.MIGRATION_MAP.copy()

    # Replace the attribute.name.update migration with our broken one
    tasks_module.MIGRATION_MAP["attribute.name.update"] = BrokenMigration

    yield

    # Restore the original migration map
    tasks_module.MIGRATION_MAP.clear()
    tasks_module.MIGRATION_MAP.update(original_map)


class TestSchemaLoadRollback(TestSchemaLifecycleBase):
    """Test that schema load rollback works correctly when migrations fail."""

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step01: dict[str, Any]
    ) -> dict[str, str]:
        """Set up initial schema and data."""
        await load_schema(db=db, schema=schema_step01)

        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

        jane = await Node.init(schema=PERSON_KIND, db=db)
        await jane.new(db=db, name="Jane", height=165, description="The famous Jane Doe")
        await jane.save(db=db)

        honda = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await honda.new(db=db, name="honda", description="Honda Motor Co., Ltd")
        await honda.save(db=db)

        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(
            db=db, name="accord", description="Honda Accord", color="#3443eb", manufacturer=honda, owner=jane
        )
        await accord.save(db=db)

        blue = await Node.init(schema=TAG_KIND, db=db)
        await blue.new(db=db, name="blue", cars=[accord], persons=[jane])
        await blue.save(db=db)

        return {
            "john": john.id,
            "jane": jane.id,
            "honda": honda.id,
            "accord": accord.id,
            "blue": blue.id,
        }

    async def test_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        """Verify initial data is set up correctly."""
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        assert len(persons) == 2

        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        assert person_schema.get_attribute(name="name") is not None

    async def test_schema_load_rollback_on_migration_failure(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        patched_migrations: None,
        initial_dataset: dict[str, str],
        schema_step02: dict[str, Any],
    ) -> None:
        """Test that schema and data are rolled back when migration fails.

        This test:
        1. Captures the original schema state
        2. Attempts to load a new schema that would trigger migrations
        3. Patches the migration to fail
        4. Verifies the schema registry is restored to original state
        5. Verifies the database schema changes are rolled back
        """
        # Capture original schema state
        person_schema_before = registry.schema.get_node_schema(name=PERSON_KIND)
        original_attr_names = {attr.name for attr in person_schema_before.attributes}
        original_schema_hash = registry.schema.get_schema_branch(name="main").get_hash()

        # Get the ID of the name attribute to include in schema for rename operation
        attr = person_schema_before.get_attribute(name="name")
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        # Attempt to load the schema - should fail and trigger rollback
        caught_exception = None
        try:
            await client.schema.load(schemas=[schema_step02])
            pytest.fail("Expected schema load to fail due to migration error")
        except httpx.HTTPStatusError as exc:
            # HTTP error indicates the server returned an error response
            caught_exception = exc
        except Exception as exc:
            # Other exceptions might occur
            caught_exception = exc

        # Verify an exception was caught
        assert caught_exception is not None, "Expected an exception to be raised"
        if isinstance(caught_exception, httpx.HTTPStatusError):
            # Verify it's a 500 Internal Server Error
            assert caught_exception.response.status_code == 500

        # Verify schema registry has been restored
        person_schema_after = registry.schema.get_node_schema(name=PERSON_KIND)
        after_attr_names = {attr.name for attr in person_schema_after.attributes}

        # The attribute names should be the same as before (no 'firstname' rename)
        assert after_attr_names == original_attr_names, (
            f"Schema was not rolled back. Expected {original_attr_names}, got {after_attr_names}"
        )

        # Verify 'name' attribute still exists (wasn't renamed to 'firstname')
        assert person_schema_after.get_attribute(name="name") is not None, (
            "The 'name' attribute should still exist after rollback"
        )

        # Verify schema hash is restored
        current_schema_hash = registry.schema.get_schema_branch(name="main").get_hash()
        assert current_schema_hash == original_schema_hash, "Schema hash was not restored after rollback"

        # Verify data is still queryable with original schema
        john = await NodeManager.get_one(db=db, id=initial_dataset["john"])
        assert john is not None, "John should still exist after rollback"
        assert john.name.value == "John", "John's name attribute should still work"

        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"name__value": "John"})
        assert len(persons) == 1, "Should be able to query by 'name' attribute after rollback"
