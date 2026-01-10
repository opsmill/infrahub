"""Unit tests for schema update rollback functionality.

Tests the full schema update flow including migrations and rollback,
closely mimicking the actual /load schema endpoint behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.query.rollback import RollbackQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


class TestSchemaUpdateAndRollback:
    """Test schema update operations with migrations and rollback.

    This test class contains a comprehensive test that mimics the actual
    /load schema endpoint behavior, including migrations.
    """

    async def test_schema_update_with_migrations_and_rollback(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_schema_db: None,
        car_accord_main: Node,
        person_john_main: Node,
    ) -> None:
        """Test full schema update flow with migrations and rollback.

        This test mimics the actual /load schema endpoint behavior:
        1. Start with existing schema (TestCar/TestPerson with 'owner' relationship)
        2. Create instance data with the relationship populated
        3. Update schema: remove relationship (state=absent), add attribute with default
        4. Run schema_apply_migrations() with same `at` timestamp
        5. Verify: relationship removed from schema, new attribute has default value
        6. Run rollback
        7. Verify: schema reverted (load from DB and compare to original)
        8. Verify: data still accessible
        """
        # Step 1 & 2: Data already created by fixtures (car_accord_main has owner relationship to person)
        # Verify the relationship exists
        loaded_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        owner = await loaded_car.owner.get_peer(db=db)
        assert owner is not None, "Car should have an owner"
        assert owner.id == person_john_main.id, "Owner should be John"

        # Save schema to DB and reload to ensure IDs are set (fixtures may only register in memory)
        current_schema = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(schema=current_schema, branch=default_branch, db=db, at=Timestamp())
        # reloaded_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        # registry.schema.set_schema_branch(name=default_branch.name, schema=reloaded_schema)

        # Step 3: Capture original state, prepare updated schema
        original_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        original_schema_copy = original_schema_branch.duplicate()
        original_car_attrs = {attr.name for attr in original_schema_branch.get(name="TestCar").attributes}

        # Get schema objects and their IDs for the update
        car_schema = original_schema_branch.get(name="TestCar")
        owner_rel = car_schema.get_relationship(name="owner")

        # Create updated schema dict with:
        # - owner relationship marked as absent (with ID to identify it)
        # - new 'status' attribute with default value
        updated_schema_dict = {
            "version": "1.0",
            "nodes": [
                {
                    "id": car_schema.id,
                    "name": "Car",
                    "namespace": "Test",
                    "attributes": [
                        {"name": "name", "kind": "Text"},
                        {"name": "nbr_seats", "kind": "Number", "optional": True},
                        {"name": "color", "kind": "Text", "default_value": "#444444", "optional": True},
                        {"name": "is_electric", "kind": "Boolean", "optional": True},
                        {"name": "transmission", "kind": "Text", "optional": True},
                        # New attribute with default value
                        {"name": "status", "kind": "Text", "optional": True, "default_value": "available"},
                    ],
                    "relationships": [
                        {
                            "id": owner_rel.id,
                            "name": "owner",
                            "peer": "TestPerson",
                            "kind": "Attribute",
                            "cardinality": "one",
                            "optional": True,
                            "state": "absent",  # Mark for deletion
                        },
                    ],
                },
            ],
        }

        # Load updated schema using the standard flow
        updated_schema_branch = original_schema_branch.duplicate()
        updated_schema_branch.load_schema(schema=SchemaRoot(**updated_schema_dict))
        # updated_schema_branch.process()

        # Get diff and validate to generate migrations
        diff = original_schema_branch.diff(other=updated_schema_branch)
        validation_result = original_schema_branch.validate_update(other=updated_schema_branch, diff=diff)

        # Verify we have migrations to run
        assert validation_result.migrations, "Should have migrations to apply"

        # Steps 3 & 4: Apply schema update and run migrations using SchemaUpdateCoordinator
        schema_update_at = Timestamp()

        coordinator = SchemaUpdateCoordinator(
            db=db,
            branch=default_branch,
            schema_manager=registry.schema,
            origin_schema=original_schema_copy,
            migration_executor=MigrationExecutor.DIRECT,
        )
        result = await coordinator.execute(
            candidate_schema=updated_schema_branch,
            at=schema_update_at,
            diff=diff,
            migrations=validation_result.migrations,
            update_db=True,
            update_registry=True,
        )
        assert result.success, f"Schema update should succeed: {result.error_messages}"

        # Step 5: Verify changes applied
        # - Relationship should be removed from schema
        updated_car_schema = registry.schema.get_node_schema(name="TestCar")
        with pytest.raises(ValueError, match="Unable to find the relationship owner"):
            updated_car_schema.get_relationship(name="owner")

        # - New attribute should exist in schema with default value
        status_attr_schema = updated_car_schema.get_attribute(name="status")
        assert status_attr_schema is not None, "New 'status' attribute should exist"
        assert status_attr_schema.default_value == "available", "Status should have default value 'available'"

        # Retrieve car instance and validate the relationship is removed and the attribute exists with the correct value
        loaded_car_after_migration = await NodeManager.get_one(db=db, id=car_accord_main.id)
        assert loaded_car_after_migration is not None, "Car should still exist after migration"

        # Verify relationship is removed
        with pytest.raises(ValueError, match="owner is not a relationship"):
            loaded_car_after_migration.get_relationship(name="owner")

        # Verify new attribute exists with default value
        status_attr = loaded_car_after_migration.get_attribute(name="status")
        assert status_attr.value == "available", (
            f"status should have default value 'available', got {status_attr.value}"
        )

        # Step 6: Run rollback
        rollback_query = await RollbackQuery.init(
            db=db,
            target_branch=default_branch,
            at=schema_update_at,
        )
        await rollback_query.execute(db=db)

        # Step 7: Verify schema reverted by loading from DB and comparing to original
        # Load fresh schema from database (this verifies DB state was rolled back)
        rolled_back_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=rolled_back_schema_branch)

        # Compare rolled back schema to original
        rolled_back_car_schema = rolled_back_schema_branch.get(name="TestCar")

        # Verify relationship is restored
        assert rolled_back_car_schema.get_relationship(name="owner") is not None, (
            "owner relationship should be restored"
        )

        # Verify new attribute is gone (rolled back)
        rolled_back_car_attrs = {attr.name for attr in rolled_back_car_schema.attributes}
        assert rolled_back_car_attrs == original_car_attrs, (
            f"Car attributes should match original. Got {rolled_back_car_attrs}, expected {original_car_attrs}"
        )
        assert "status" not in rolled_back_car_attrs, "status attribute should be rolled back"

        # Step 8: Verify data still accessible
        loaded_car = await NodeManager.get_one(db=db, id=car_accord_main.id, prefetch_relationships=True)
        assert loaded_car is not None, "Car should still exist"
        assert loaded_car.name.value == "accord", "Car name should still be accessible"

        # Validate relationship exists again
        owner_rel = loaded_car.get_relationship(name="owner")
        owner_after_rollback = await owner_rel.get_peer(db=db)
        assert owner_after_rollback is not None, "owner relationship should be restored after rollback"
        assert owner_after_rollback.id == person_john_main.id, "Owner should still be John after rollback"

        # Verify status attribute is gone (rolled back)
        with pytest.raises(ValueError, match="status is not an attribute"):
            loaded_car.get_attribute(name="status")
