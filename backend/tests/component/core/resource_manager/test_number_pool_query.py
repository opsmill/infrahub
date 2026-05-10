from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import (
    NumberPoolGetAllocated,
    NumberPoolGetReserved,
    NumberPoolGetUsed,
    PoolChangeReserved,
)
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter

REQUEST = NodeSchema(
    name="Request",
    namespace="Test",
    label="Request",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(name="number", kind="NumberPool", optional=False, read_only=True, unique=True),
    ],
)

INCIDENT = NodeSchema(
    name="Incident",
    namespace="Test",
    label="Incident",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(name="number", kind="NumberPool", optional=False, read_only=True, unique=True),
    ],
)


@pytest.fixture
async def register_test_schema(default_branch: Branch, register_core_models_schema: SchemaBranch) -> SchemaBranch:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    schema = SchemaRoot(
        version="1.0",
        nodes=[REQUEST, INCIDENT],
    )
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    return schema_branch


@pytest.fixture
async def run_number_pool_validation(db: InfrahubDatabase) -> None:
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    snps = SchemaNumberPoolSynchronizer(
        db=db,
        schema_manager=registry.schema,
        upserter=upserter,
    )
    await snps.run()


async def create_objects(db: InfrahubDatabase, schema: NodeSchema, branch: str, start: int, end: int) -> list[Node]:
    """Helper function to create incidents."""
    nodes = []
    for idx in range(start, end + 1):
        incident = await Node.init(db=db, schema=schema, branch=branch)
        await incident.new(db=db, title=f"{schema.name} #{idx}")
        await incident.save(db=db)
        nodes.append(incident)
    return nodes


async def get_used_numbers_in_pool(db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch) -> list[int]:
    """Helper function to get used numbers in a pool."""
    query = await NumberPoolGetUsed.init(db=db, branch=branch, pool=pool, branch_agnostic=True)
    await query.execute(db=db)
    return sorted([result.value for result in query.iter_results()])


async def get_reservations(db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch) -> dict[str, int]:
    query1 = await NumberPoolGetReserved.init(db=db, pool_id=pool.get_id(), branch=branch)
    await query1.execute(db=db)
    return {item.identifier: item.value for item in query1.get_reservations()}


class TestNumberPoolGetUsed:
    async def test_NumberPoolGetUsed(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)

        # Identify the NumberPool for each model
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        assert len(pools) == 2
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Validate that the incident NumberPool has 3 used values
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3]

        # Create a new branch and add more incidents
        # Ensure the query returns all used numbers across branches
        branch2 = await create_branch(db=db, branch_name="branch2")
        await create_objects(db=db, schema=incident_schema, branch=branch2.name, start=4, end=7)

        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3, 4, 5, 6, 7]

        # Delete the branch and validate that the numbers allocated previously are available
        await branch2.delete(db=db)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3]

        # Create a new branch and add more incidents
        # to ensure the query returns all used numbers across branches
        branch3 = await create_branch(db=db, branch_name="branch3")
        await create_objects(db=db, schema=incident_schema, branch=branch3.name, start=11, end=13)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3, 4, 5, 6]

        # Delete the branch and validate that the numbers allocated previously are available
        await branch3.delete(db=db)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3]

        # Delete nodes in main and ensure the numbers are reallocated
        await incidents[1].delete(db=db)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 3]


class TestNumberPoolGetAllocated:
    async def test_NumberPoolGetAllocated_returns_identifier(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Test that NumberPoolGetAllocated returns the identifier (node UUID) from the IS_RESERVED relationship."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )

        # Act
        await query.execute(db=db)
        results = query.get_data()

        assert len(results) == 3
        # Build a lookup by allocated value
        results_by_value = {r.value: r for r in results}

        # Each allocated result should have the identifier set to the node UUID
        for idx, incident in enumerate(incidents, start=1):
            result = results_by_value[idx]
            assert result.identifier == incident.get_id()

    async def test_NumberPoolGetAllocated_excludes_deleted(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """When a node is deleted on main branch which is the only branch having this allocated value,
        NumberPoolGetAllocated should not return it.
        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        await incident2.delete(db=db)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 3], (
            f"Expected deleted allocation (value=2) to be excluded on branch, got {allocated_values}"
        )

    async def test_NumberPoolGetAllocated_includes_allocation_active_on_other_branch(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """When a node created on main is deleted on a branch, NumberPoolGetAllocated still returns it."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Create a branch and delete incident #2 on that branch
        branch2 = await create_branch(db=db, branch_name="branch2")
        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=branch2)
        await incident2.delete(db=db)

        # Query on branch2 — the allocation is still active on main, so it should appear
        query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=branch2, branch_agnostic=True)
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 2, 3], (
            f"Expected allocation (value=2) to remain visible (active on main), got {allocated_values}"
        )

    async def test_NumberPoolGetAllocated_includes_allocation_when_source_cleared_on_branch(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """When HAS_SOURCE is cleared on a branch, the allocation still appears because it is active on main."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Create a branch and clear the source on incident #2's number attribute
        br1 = await create_branch(db=db, branch_name="br1")
        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2.get_attribute("number").clear_source()
        await incident2.save(db=db)

        # Query on br1 — the allocation is still active on main, so it should appear
        query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=br1, branch_agnostic=True)
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 2, 3], (
            f"Expected allocation (value=2) to remain visible (active on main), got {allocated_values}"
        )

    async def test_NumberPoolGetAllocated_excludes_allocation_when_source_cleared_on_same_branch(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """When HAS_SOURCE is cleared on the same branch it was created on and there are no additional branches which contain
        this allocation, the allocation must not appear.
        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        incident2.get_attribute("number").clear_source()
        await incident2.save(db=db)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 3], (
            f"Expected allocation (value=2) to be excluded after HAS_SOURCE was cleared on the same branch, "
            f"got {allocated_values}"
        )

    async def test_NumberPoolGetAllocated_requires_to_is_null_after_cross_branch_and_same_branch_clear(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """1. Create incidents on main
        2. Fork br1 and clear the source on br1
        3. Clear the source on main
        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        br1 = await create_branch(db=db, branch_name="br1")

        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").clear_source()
        await incident2_on_br1.save(db=db)

        incident2_on_main = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        incident2_on_main.get_attribute("number").clear_source()
        await incident2_on_main.save(db=db)

        # Resulting state for incident #2's number attribute:
        #  - main edge:  status="active", to=<cleared_at>
        #  - br1 edge:   status="deleted", to=NULL

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 3], f"Expected allocation (value=2) to be excluded. Got {allocated_values}."

    async def test_NumberPoolGetAllocated_includes_allocation_when_source_cleared_then_reassigned_on_branch(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Scenario: on a child branch, source=pool -> source=null -> source=pool again; then the
        main-branch active edge is closed so that it cannot satisfy the query on its own.
        """
        # Step 1: creation on main.
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Step 2: fork br1 and clear the source on br1
        br1 = await create_branch(db=db, branch_name="br1")
        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").clear_source()
        await incident2_on_br1.save(db=db)

        # Step 3: re-assign the source back to the pool on br1
        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").set_source(incident_pool.get_id())
        await incident2_on_br1.save(db=db)

        # Step 4: close the main-branch active edge by clearing the source on main
        incident2_on_main = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        incident2_on_main.get_attribute("number").clear_source()
        await incident2_on_main.save(db=db)

        query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=br1, branch_agnostic=True)
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 2, 3], (
            f"Expected allocation (value=2) to be counted after being re-assigned to the pool on br1; "
            f"got {allocated_values}"
        )

    async def test_NumberPoolGetAllocated_excludes_allocation_after_merging_cleared_source(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Fork a branch from main, clear the source on forked branch. Merge the forked branch back into main. The value
        should not be allocated anymore.
        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Fork br1 and clear the source on br1.
        br1 = await create_branch(db=db, branch_name="br1-clear-then-merge")
        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").clear_source()
        await incident2_on_br1.save(db=db)

        # Merge br1 back into main.
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=br1)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=br1)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=br1)
        await diff_merger.merge_graph(at=Timestamp())

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 3], (
            f"Expected allocation (value=2) to be excluded after merging the HAS_SOURCE removal "
            f"from br1 into main; got {allocated_values}"
        )


class TestPoolChangeReserved:
    async def test_PoolChangeReserved(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)
        incident = incidents[1]

        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        assert len(pools) == 2
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        reservations_before = await get_reservations(db=db, pool=incident_pool, branch=default_branch)
        assert len(reservations_before) == 3
        assert reservations_before[incident.get_id()] == 2

        query = await PoolChangeReserved.init(
            db=db, existing_identifier=incident.get_id(), new_identifier="new_id", branch=default_branch
        )
        await query.execute(db=db)

        reservations_before = await get_reservations(db=db, pool=incident_pool, branch=default_branch)
        assert len(reservations_before) == 3
        assert reservations_before["new_id"] == 2
