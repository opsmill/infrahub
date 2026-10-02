from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

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
from tests.component.pools.helpers import NumberPoolRepositoryFailingOnDelete
from tests.helpers.number_pool import register_and_provision_number_pools

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
