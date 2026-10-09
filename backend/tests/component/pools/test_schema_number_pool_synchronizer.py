from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters, NumberPoolRangeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.pools.scope import AllocationScopeResolver
from tests.component.pools.helpers import NumberPoolRepositoryFailingOnDelete
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_POOL_SCHEMA, register_and_provision_number_pools
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_pool_repository import NumberPoolRangeStoreFactory

COUNTER_KIND = "TestingCounter"


def counter_schema(parameters: NumberPoolParameters) -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Counter",
                namespace="Testing",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(
                        name="counter",
                        kind="NumberPool",
                        optional=False,
                        read_only=True,
                        unique=True,
                        parameters=parameters,
                    ),
                ],
            )
        ]
    )


async def provision_pool(db: InfrahubDatabase, branch: Branch, parameters: NumberPoolParameters) -> str:
    """Declare the counter attribute on the branch, let the synchronizer create its pool, and return the pool id."""
    await register_and_provision_number_pools(db=db, branch=branch, schema=counter_schema(parameters=parameters))
    pools = await NodeManager.query(
        db=db,
        schema=CoreNumberPool,
        filters={"node__value": COUNTER_KIND, "node_attribute__value": "counter"},
        branch_agnostic=True,
    )
    assert len(pools) == 1
    return pools[0].get_id()


async def redeclare(
    db: InfrahubDatabase,
    branch: Branch,
    parameters: NumberPoolParameters,
    range_store_factory: NumberPoolRangeStoreFactory = NumberPoolRepository,
) -> None:
    """Load a new counter declaration on the branch and run the synchronizer again."""
    registry.schema.register_schema(schema=counter_schema(parameters=parameters), branch=branch.name)

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    await SchemaNumberPoolSynchronizer(
        db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=range_store_factory
    ).run()


async def ranges_of(db: InfrahubDatabase, pool_id: str) -> list[tuple[int, int, int | None]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    return [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]


async def shorthand_of(db: InfrahubDatabase, pool_id: str) -> tuple[int | None, int | None]:
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    return (pool.get_attribute("start_range").value, pool.get_attribute("end_range").value)


async def test_default_branch_declaration_adds_removes_and_reweights_ranges(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Ranges follow the default-branch declaration as ranges are added, reweighted and removed."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    await redeclare(
        db=db,
        branch=default_branch,
        parameters=NumberPoolParameters(
            ranges=[
                NumberPoolRangeParameters(start=1, end=100, weight=5),
                NumberPoolRangeParameters(start=200, end=300),
            ]
        ),
    )
    assert await ranges_of(db=db, pool_id=pool_id) == [(1, 100, 5), (200, 300, None)]
    assert await shorthand_of(db=db, pool_id=pool_id) == (None, None)

    await redeclare(
        db=db,
        branch=default_branch,
        parameters=NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=200, end=300)]),
    )
    assert await ranges_of(db=db, pool_id=pool_id) == [(200, 300, None)]
    assert await shorthand_of(db=db, pool_id=pool_id) == (200, 300)


async def test_reconciliation_keeps_the_numbers_already_handed_out(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Objects keep their numbers and the pool keeps accounting for them after its ranges change."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    counters = []
    for name in ("first", "second"):
        counter = await Node.init(db=db, schema=COUNTER_KIND, branch=default_branch)
        await counter.new(db=db, name=name)
        await counter.save(db=db)
        counters.append(counter)
    assert [counter.get_attribute("counter").value for counter in counters] == [1, 2]

    await redeclare(
        db=db,
        branch=default_branch,
        parameters=NumberPoolParameters(
            ranges=[NumberPoolRangeParameters(start=1, end=50), NumberPoolRangeParameters(start=200, end=300)]
        ),
    )

    reloaded = await NodeManager.get_many(db=db, ids=[counter.get_id() for counter in counters], branch=default_branch)
    assert sorted(node.get_attribute("counter").value for node in reloaded.values()) == [1, 2]
    repository = NumberPoolRepository(db=db)
    for counter in counters:
        reserved = await repository.get_reservation(pool_id=pool_id, branch=default_branch, identifier=counter.get_id())
        assert reserved == counter.get_attribute("counter").value


@pytest.mark.xfail(strict=True, reason="A declaration using neither spelling keeps the stored ranges on schema load")
async def test_declaration_without_range_empties_the_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A declaration using neither spelling is legal and leaves the pool with no range and a null shorthand."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )

    await redeclare(db=db, branch=default_branch, parameters=NumberPoolParameters())

    assert await ranges_of(db=db, pool_id=pool_id) == []
    assert await shorthand_of(db=db, pool_id=pool_id) == (None, None)


async def test_failed_reconciliation_leaves_the_ranges_untouched(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A reconciliation that cannot complete leaves the pool's ranges and shorthand as they were."""
    pool_id = await provision_pool(
        db=db,
        branch=default_branch,
        parameters=NumberPoolParameters(
            ranges=[NumberPoolRangeParameters(start=1, end=100), NumberPoolRangeParameters(start=200, end=300)]
        ),
    )
    before = await ranges_of(db=db, pool_id=pool_id)

    # The first range is rewritten to 1-50 before the second one fails to go away.
    with pytest.raises(RuntimeError, match="range delete failed"):
        await redeclare(
            db=db,
            branch=default_branch,
            parameters=NumberPoolParameters(start_range=1, end_range=50),
            range_store_factory=NumberPoolRepositoryFailingOnDelete,
        )

    assert await ranges_of(db=db, pool_id=pool_id) == before
    assert await shorthand_of(db=db, pool_id=pool_id) == (None, None)


async def test_declaration_on_another_branch_leaves_the_pool_untouched(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Only the default-branch declaration drives the ranges of a pool declared there."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    before = await ranges_of(db=db, pool_id=pool_id)
    other_branch = await create_branch(db=db, branch_name="counter-ranges")

    await redeclare(db=db, branch=other_branch, parameters=NumberPoolParameters(start_range=500, end_range=600))

    assert await ranges_of(db=db, pool_id=pool_id) == before
    assert await shorthand_of(db=db, pool_id=pool_id) == (1, 100)


async def run_synchronizer(db: InfrahubDatabase) -> None:
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    await SchemaNumberPoolSynchronizer(
        db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
    ).run()


async def create_device_pool(db: InfrahubDatabase, name: str, scope: list[str]) -> str:
    """Create a user pool over the device's vlan_id with the scope resolved on the default branch, and return its id."""
    allocation_scope = AllocationScopeResolver(
        schema_branch=registry.schema.get_schema_branch(name=registry.default_branch)
    ).resolve(kind=SCOPED_DEVICE.kind, entries=scope)
    pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=SCOPED_DEVICE.kind,
        node_attribute="vlan_id",
        start_range=1,
        end_range=10,
        allocation_scope=None if allocation_scope.is_empty else allocation_scope.to_stored(),
    )
    await pool.save(db=db)
    return pool.get_id()


async def stored_scope_of(db: InfrahubDatabase, pool_id: str) -> list[dict[str, str]] | None:
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    return pool.allocation_scope.value


async def scope_writes_of(db: InfrahubDatabase, pool_id: str) -> int:
    """Return how many values the pool's allocation_scope attribute has held, one more after each write."""
    query = """
    MATCH (:Node {uuid: $pool_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "allocation_scope"})-[edge:HAS_VALUE]->()
    RETURN count(edge) AS writes
    """
    results = await db.execute_query(query=query, params={"pool_id": pool_id})
    return results[0]["writes"]


def default_device() -> NodeSchema:
    device = registry.schema.get_schema_branch(name=registry.default_branch).get_node(name=SCOPED_DEVICE.kind)
    assert isinstance(device, NodeSchema)
    return device


async def test_renaming_scope_elements_rewrites_their_stored_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A renamed relationship and a renamed attribute keep their ids and the stored names follow the new names."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    scoped_pool_id = await create_device_pool(db=db, name="vlan-per-site-and-role", scope=["site", "role"])
    unscoped_pool_id = await create_device_pool(db=db, name="vlan", scope=[])
    device = default_device()
    site_id = device.get_relationship(name="site").id
    role_id = device.get_attribute(name="role").id
    unscoped_writes = await scope_writes_of(db=db, pool_id=unscoped_pool_id)

    device.get_relationship(name="site").name = "location"
    device.get_attribute(name="role").name = "function"
    await load_schema(db=db, schema=SchemaRoot(nodes=[device]), update_db=True)
    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=scoped_pool_id) == [
        {"id": site_id, "name": "location"},
        {"id": role_id, "name": "function"},
    ]
    assert await stored_scope_of(db=db, pool_id=unscoped_pool_id) is None
    assert await scope_writes_of(db=db, pool_id=unscoped_pool_id) == unscoped_writes


async def test_current_scope_names_are_not_rewritten(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool whose stored names match the default branch keeps its stored scope without a new write."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    pool_id = await create_device_pool(db=db, name="vlan-per-site", scope=["site"])
    before = await stored_scope_of(db=db, pool_id=pool_id)
    writes = await scope_writes_of(db=db, pool_id=pool_id)

    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=pool_id) == before
    assert await scope_writes_of(db=db, pool_id=pool_id) == writes


async def test_renaming_on_another_branch_keeps_the_stored_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Only the default branch names the scope elements, so a rename on another branch leaves the stored names."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    pool_id = await create_device_pool(db=db, name="vlan-per-site", scope=["site"])
    before = await stored_scope_of(db=db, pool_id=pool_id)
    other_branch = await create_branch(db=db, branch_name="scope-rename")
    device = registry.schema.get_schema_branch(name=other_branch.name).get_node(name=SCOPED_DEVICE.kind)
    device.get_relationship(name="site").name = "location"

    await load_schema(db=db, schema=SchemaRoot(nodes=[device]), branch_name=other_branch.name, update_db=True)
    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=pool_id) == before


async def test_schema_created_pool_stale_scope_name_is_rewritten(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool the schema created gets the name the default branch gives the element its stored id refers to."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    counter = registry.schema.get_schema_branch(name=registry.default_branch).get_node(name=COUNTER_KIND)
    name_id = counter.get_attribute(name="name").id
    assert name_id
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    pool.allocation_scope.value = [{"id": name_id, "name": "label"}]
    await pool.save(db=db)

    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=pool_id) == [{"id": name_id, "name": "name"}]


async def test_declaration_the_default_branch_cannot_resolve_leaves_later_pools_created(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A declared scope the default branch no longer resolves creates no pool, and the other declarations get theirs."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    scoped_branch = await create_branch(db=db, branch_name="scope-gone")
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.append(
        AttributeSchema(
            name="vlan_index",
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(start_range=1, end_range=10, allocation_scope=["site"]),
        )
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[device]), branch=scoped_branch.name)
    default_schema = registry.schema.get_schema_branch(name=registry.default_branch)
    default_device_without_site = default_schema.get_node(name=SCOPED_DEVICE.kind)
    default_device_without_site.relationships = [
        relationship for relationship in default_device_without_site.relationships if relationship.name != "site"
    ]
    default_schema.set(name=SCOPED_DEVICE.kind, schema=default_device_without_site)
    counter_branch = await create_branch(db=db, branch_name="counter-pool")
    registry.schema.register_schema(
        schema=counter_schema(parameters=NumberPoolParameters(start_range=1, end_range=100)), branch=counter_branch.name
    )

    await run_synchronizer(db=db)

    device_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": SCOPED_DEVICE.kind}, branch_agnostic=True
    )
    counter_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": COUNTER_KIND}, branch_agnostic=True
    )
    assert (len(device_pools), len(counter_pools)) == (0, 1)
