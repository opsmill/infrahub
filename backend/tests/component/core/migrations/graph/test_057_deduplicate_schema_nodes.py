from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m057_deduplicate_schema_nodes import (
    FindDuplicateSchemaNodesQuery,
    Migration057,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestMigration057:
    async def _register_and_load_user_schemas(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schemas: list[NodeSchema],
    ) -> None:
        """Register user-defined schemas and load them to the DB."""
        manager = registry.schema
        user_schema = SchemaRoot(
            version=internal_schema["version"],
            nodes=schemas,
        )
        schema_branch = manager.register_schema(schema=user_schema, branch=branch.name)
        kind_names = [s.kind for s in schemas]
        await manager.load_schema_to_db(schema=schema_branch, db=db, branch=branch, limit=kind_names)

    async def _duplicate_schemas(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        kind_names: list[str],
    ) -> None:
        """Create duplicates of schemas by loading copies with id=None (forces new UUIDs)."""
        manager = registry.schema
        schema_branch = manager.get_schema_branch(name=branch.name)
        for kind_name in kind_names:
            item = schema_branch.get(name=kind_name, duplicate=True)
            item.id = None
            for attr in item.attributes:
                if not attr.inherited:
                    attr.id = None
            for rel in item.relationships:
                if not rel.inherited:
                    rel.id = None
            await manager.load_node_to_db(node=item, branch=branch, db=db, at=Timestamp(), user_id="migration-test")

    async def test_basic_deduplication(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_internal_models_schema_scope_class: SchemaBranch,
    ) -> None:
        """Test that the migration removes duplicate schema nodes on the default branch."""
        schemas = [
            NodeSchema(
                name="BasicCar",
                namespace="Test",
                description="A basic car",
                default_filter="name__value",
                generate_profile=False,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="color", kind="Text", optional=True),
                ],
            ),
        ]
        await self._register_and_load_user_schemas(db=db, branch=default_branch_scope_class, schemas=schemas)
        await self._duplicate_schemas(db=db, branch=default_branch_scope_class, kind_names=[s.kind for s in schemas])

        # Verify duplicates exist
        query = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query.execute(db=db)
        duplicates = query.get_duplicates()
        assert len(duplicates) > 0, "Expected to find duplicate schema nodes before migration"

        # Execute the migration
        migration = Migration057()
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors

        # Verify no duplicates remain
        query2 = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query2.execute(db=db)
        assert len(query2.get_duplicates()) == 0, "Expected no duplicates after migration"

    async def test_keeps_node_with_latest_property_update(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_internal_models_schema_scope_class: SchemaBranch,
    ) -> None:
        """Test that migration keeps the node with the most recently updated property."""
        manager = registry.schema
        schemas = [
            NodeSchema(
                name="ConflictCar",
                namespace="Test",
                description="Default conflict car description",
                default_filter="name__value",
                generate_profile=False,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                ],
            ),
        ]

        # Register and load user schemas
        await self._register_and_load_user_schemas(db=db, branch=default_branch_scope_class, schemas=schemas)

        # Capture the original node (with its UUID) before creating duplicates
        schema_branch = manager.get_schema_branch(name=default_branch_scope_class.name)
        original = schema_branch.get(name="TestConflictCar", duplicate=True)
        original_uuid = original.id

        # Create a duplicate (newer IS_PART_OF timestamp)
        await self._duplicate_schemas(db=db, branch=default_branch_scope_class, kind_names=["TestConflictCar"])

        # Update description on the original so its HAS_VALUE.from is the latest
        original.description = "Updated description on original TestConflictCar"
        await manager.update_node_in_db(
            db=db, node=original, user_id="migration-test", at=Timestamp(), branch=default_branch_scope_class
        )

        # Verify duplicates exist and query designates the original as keep_uuid
        query = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query.execute(db=db)
        duplicates = query.get_duplicates()
        conflict_dups = [d for d in duplicates if d.kind == "TestConflictCar"]
        assert len(conflict_dups) > 0, "Expected to find duplicate TestConflictCar"
        for d in conflict_dups:
            assert d.keep_uuid == original_uuid, (
                f"Expected to keep original uuid={original_uuid}, but query chose uuid={d.keep_uuid}"
            )

        # Execute the migration
        migration = Migration057()
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors

        # Verify no duplicates remain
        query2 = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query2.execute(db=db)
        assert len(query2.get_duplicates()) == 0, "Expected no duplicates after migration"

        # Verify the surviving node has the updated description
        verify_manager = SchemaManager()
        registry.schema = verify_manager
        verify_manager.register_schema(schema=SchemaRoot(**internal_schema))
        loaded_schema = await verify_manager.load_schema_from_db(db=db, branch=default_branch_scope_class)
        car = loaded_schema.get(name="TestConflictCar")
        assert car.description == "Updated description on original TestConflictCar"
        assert car.id == original_uuid, "Expected the original node to be kept after migration"

    async def test_branch_schema_preserved(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_internal_models_schema_scope_class: SchemaBranch,
    ) -> None:
        """Test that schema modifications on a branch are preserved after deduplication on default."""
        manager = registry.schema

        schemas = [
            NodeSchema(
                name="BranchCar",
                namespace="Test",
                description="Default branch car description",
                default_filter="name__value",
                generate_profile=False,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="color", kind="Text", optional=True),
                ],
            ),
        ]

        # Register and load user schemas on the default branch
        await self._register_and_load_user_schemas(db=db, branch=default_branch_scope_class, schemas=schemas)

        # Create a branch before creating duplicates
        branch2 = await create_branch(db=db, branch_name="branch2-m057")

        # Modify TestBranchCar description on branch2
        branch2_schema = manager.get_schema_branch(name=branch2.name)
        car = branch2_schema.get(name="TestBranchCar", duplicate=True)
        car.description = "Branch2 modified car"
        await manager.update_node_in_db(db=db, node=car, user_id="migration-test", at=Timestamp(), branch=branch2)

        # Create duplicates on default branch
        await self._duplicate_schemas(db=db, branch=default_branch_scope_class, kind_names=["TestBranchCar"])

        # Verify duplicates exist on default branch
        query = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query.execute(db=db)
        duplicates = query.get_duplicates()
        branch_car_dups = [d for d in duplicates if d.kind == "TestBranchCar"]
        assert len(branch_car_dups) > 0, "Expected to find duplicate TestBranchCar"

        # Execute the migration
        migration = Migration057()
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors

        # Verify no duplicates remain on default branch
        query2 = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query2.execute(db=db)
        assert len(query2.get_duplicates()) == 0, "Expected no duplicates after migration"

        # Reload schemas and verify both branches
        verify_manager = SchemaManager()
        registry.schema = verify_manager
        verify_manager.register_schema(schema=SchemaRoot(**internal_schema))

        # Verify default branch schema
        default_schema = await verify_manager.load_schema_from_db(db=db, branch=default_branch_scope_class)
        car_default = default_schema.get(name="TestBranchCar")
        assert car_default.description == "Default branch car description"
        assert car_default.get_attribute(name="name") is not None
        assert car_default.get_attribute(name="color") is not None

        # Verify branch2 schema has the modified description
        branch_schema = await verify_manager.load_schema_from_db(db=db, branch=branch2)
        car_branch = branch_schema.get(name="TestBranchCar")
        assert car_branch.description == "Branch2 modified car"
        assert car_branch.get_attribute(name="name") is not None
        assert car_branch.get_attribute(name="color") is not None
