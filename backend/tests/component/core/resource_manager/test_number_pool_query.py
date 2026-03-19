import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
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
from infrahub.database import InfrahubDatabase
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


async def test_NumberPoolGetUsed(
    db: InfrahubDatabase, register_test_schema: SchemaBranch, default_branch: Branch, run_number_pool_validation: None
) -> None:
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)

    # Identify the NumberPool for each model
    pools: list[CoreNumberPool] = await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch)
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


async def test_NumberPoolGetAllocated_returns_identifier(
    db: InfrahubDatabase,
    register_test_schema: SchemaBranch,
    default_branch: Branch,
    run_number_pool_validation: None,
) -> None:
    """Test that NumberPoolGetAllocated returns the identifier (node UUID) from the IS_RESERVED relationship."""
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    pools: list[CoreNumberPool] = await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch)
    incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

    query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True)

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
    db: InfrahubDatabase,
    register_test_schema: SchemaBranch,
    default_branch: Branch,
    run_number_pool_validation: None,
) -> None:
    """When a node is deleted on main branch, NumberPoolGetAllocated should not return it."""
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    pools: list[CoreNumberPool] = await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch)
    incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

    incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
    await incident2.delete(db=db)

    query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True)
    await query.execute(db=db)
    results = query.get_data()

    allocated_values = sorted([r.value for r in results])
    assert allocated_values == [1, 3], (
        f"Expected deleted allocation (value=2) to be excluded on branch, got {allocated_values}"
    )


async def test_NumberPoolGetAllocated_includes_allocation_active_on_other_branch(
    db: InfrahubDatabase,
    register_test_schema: SchemaBranch,
    default_branch: Branch,
    run_number_pool_validation: None,
) -> None:
    """When a node created on main is deleted on a branch, NumberPoolGetAllocated still returns it.

    The allocation is still active on main (HAS_SOURCE edge remains active there),
    so it should appear in the allocated list regardless of the branch-local deletion.
    """
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    pools: list[CoreNumberPool] = await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch)
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
    db: InfrahubDatabase,
    register_test_schema: SchemaBranch,
    default_branch: Branch,
    run_number_pool_validation: None,
) -> None:
    """When HAS_SOURCE is cleared on a branch, the allocation still appears because it is active on main.

    Setup: 3 incidents allocated on default branch → values [1, 2, 3].
    Then on br1, clear the source of incident #2's number attribute.
    The default branch still has an active HAS_SOURCE edge for incident #2,
    so the allocation remains visible — it is still allocated from the pool's perspective.
    """
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    pools: list[CoreNumberPool] = await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch)
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


async def test_PoolChangeReserved(
    db: InfrahubDatabase, register_test_schema: SchemaBranch, default_branch: Branch, run_number_pool_validation: None
) -> None:
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)
    incident = incidents[1]

    pools: list[CoreNumberPool] = await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch)
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
