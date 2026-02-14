from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, MetadataOptions, NumberPoolType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m063_consolidate_duplicate_number_pools import Migration063
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetReserved
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestMigration063:
    @pytest.fixture
    async def duplicate_pool_setup(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
    ) -> dict:
        """Load the same schema with duplicate CoreNumberPools on 3 branches.

        For each branch: create a CoreNumberPool, then load a TestDevice schema whose
        serial_number attribute references that pool via number_pool_id. Creating a device
        on each branch allocates from the pool, producing IS_RESERVED and HAS_SOURCE edges.
        This mirrors the real bug where loading the same schema on multiple branches
        creates separate pools for the same node + node_attribute.
        """
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        # Create all branches BEFORE loading any schemas
        branches = []
        for i in range(3):
            branch = await create_branch(db=db, branch_name=f"pool-branch-{i}")
            branches.append(branch)

        pool_uuids = []
        device_ids = []

        for branch in branches:
            # Create a CoreNumberPool (mimics the pool auto-created per-branch in the real bug)
            pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
            await pool.new(
                db=db,
                name=f"pool-{branch.name}",
                node="TestDevice",
                node_attribute="serial_number",
                start_range=1,
                end_range=1000,
                pool_type=NumberPoolType.SCHEMA.value,
            )
            await pool.save(db=db)
            pool_uuids.append(pool.id)

            # Load a TestDevice schema with serial_number referencing this pool
            device_schema_dict: dict = {
                "nodes": [
                    {
                        "name": "Device",
                        "namespace": "Test",
                        "default_filter": "name__value",
                        "display_labels": ["name__value"],
                        "attributes": [
                            {"name": "name", "kind": "Text", "unique": True},
                            {
                                "name": "serial_number",
                                "kind": "NumberPool",
                                "read_only": True,
                                "unique": True,
                                "parameters": {
                                    "number_pool_id": pool.id,
                                    "start_range": 1,
                                    "end_range": 1000,
                                },
                            },
                        ],
                    }
                ]
            }
            schema = SchemaRoot(**device_schema_dict)
            schema_branch = registry.schema.register_schema(schema=schema, branch=branch.name)
            await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=branch, limit=["TestDevice"])

            # Creating a device allocates from the pool (IS_RESERVED + HAS_SOURCE edges)
            device = await Node.init(db=db, schema="TestDevice", branch=branch)
            await device.new(db=db, name=f"device-{branch.name}")
            await device.save(db=db)
            device_ids.append(device.id)

        return {
            "branches": branches,
            "pool_uuids": pool_uuids,
            "device_ids": device_ids,
        }

    async def _validate_consolidation(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branches: list[Branch],
        pool_uuids: list[str],
        device_ids: list[str],
    ) -> None:
        """Assert that only the oldest pool survives and all references point to it."""
        oldest_uuid = pool_uuids[0]

        # Only the oldest pool should survive
        survivor = await NodeManager.get_one(db=db, id=oldest_uuid, branch_agnostic=True, raise_on_error=True)
        assert survivor is not None
        for deleted_uuid in pool_uuids[1:]:
            with pytest.raises(NodeNotFoundError):
                await NodeManager.get_one(db=db, id=deleted_uuid, branch_agnostic=True, raise_on_error=True)

        # All IS_RESERVED edges should now be on the survivor pool
        query = await NumberPoolGetReserved.init(
            db=db, branch=default_branch, pool_id=oldest_uuid, branch_agnostic=True
        )
        await query.execute(db=db)
        reservations = query.get_data()
        assert {r.identifier for r in reservations} == set(device_ids)

        # All HAS_SOURCE edges should now point to the oldest pool
        for branch, device_id in zip(branches, device_ids, strict=True):
            device = await NodeManager.get_one(
                db=db, id=device_id, branch=branch, include_metadata=MetadataOptions.LINKED_NODES, raise_on_error=True
            )
            assert device.get_attribute("serial_number").source_id == oldest_uuid

        # SchemaAttribute parameters should all reference the oldest pool
        for branch in branches:
            fresh_schema = await registry.schema.load_schema_from_db(db=db, branch=branch, validate_schema=False)
            test_device = fresh_schema.get_node(name="TestDevice")
            attr = test_device.get_attribute(name="serial_number")
            assert attr.parameters.number_pool_id == oldest_uuid

    async def test_consolidates_duplicate_pools(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        duplicate_pool_setup: dict,
    ) -> None:
        branches = duplicate_pool_setup["branches"]
        pool_uuids = duplicate_pool_setup["pool_uuids"]
        device_ids = duplicate_pool_setup["device_ids"]

        # First run
        async with db.start_session() as dbs:
            migration = Migration063()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        await self._validate_consolidation(
            db=db,
            default_branch=default_branch,
            branches=branches,
            pool_uuids=pool_uuids,
            device_ids=device_ids,
        )

        # Second run (idempotency) — should succeed with no changes
        async with db.start_session() as dbs:
            migration = Migration063()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        await self._validate_consolidation(
            db=db,
            default_branch=default_branch,
            branches=branches,
            pool_uuids=pool_uuids,
            device_ids=device_ids,
        )

    async def test_no_duplicates_is_noop(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        """When there are no duplicates, migration should complete successfully with no changes."""
        pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="solo-pool",
            node="SoloDevice",
            node_attribute="solo_attr",
            start_range=1,
            end_range=100,
            pool_type=NumberPoolType.SCHEMA.value,
        )
        await pool.save(db=db)

        async with db.start_session() as dbs:
            migration = Migration063()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        # Pool should still exist
        existing = await NodeManager.query(
            db=db,
            schema=InfrahubKind.NUMBERPOOL,
            filters={"name__value": "solo-pool"},
        )
        assert len(existing) == 1
