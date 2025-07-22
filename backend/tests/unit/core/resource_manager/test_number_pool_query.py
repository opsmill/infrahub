import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetReserved, NumberPoolGetUsed, PoolChangeReserved
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

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
async def register_test_schema(default_branch: Branch, register_core_models_schema) -> SchemaBranch:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    schema = SchemaRoot(
        version="1.0",
        nodes=[REQUEST, INCIDENT],
    )
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    return schema_branch


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
    db: InfrahubDatabase, register_test_schema: SchemaBranch, default_branch: Branch
) -> None:
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)

    # Identify the NumberPool for each model
    pools: list[CoreNumberPool] = await registry.schema.query(
        db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch.name
    )
    assert len(pools) == 2
    incident_pool = next(pool for pool in pools if pool.node.value == INCIDENT.kind)

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


async def test_PoolChangeReserved(
    db: InfrahubDatabase, register_test_schema: SchemaBranch, default_branch: Branch
) -> None:
    incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
    request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

    incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
    await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)
    incident = incidents[1]

    pools: list[CoreNumberPool] = await registry.schema.query(
        db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch.name
    )
    assert len(pools) == 2
    incident_pool = next(pool for pool in pools if pool.node.value == INCIDENT.kind)

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
