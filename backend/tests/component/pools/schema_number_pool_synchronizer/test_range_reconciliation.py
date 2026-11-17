"""The synchronizer reconciles the ranges of a schema pool with the ranges the schema declares."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters, NumberPoolRangeParameters
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPoolReader
from tests.component.pools.helpers import (
    NumberPoolRepositoryFailingOnDelete,
    NumberPoolRepositoryRecordingWritesFactory,
)
from tests.component.pools.schema_number_pool_synchronizer.helpers import COUNTER_KIND, counter_schema, provision_pool

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_pool_repository import NumberPoolRangeStoreFactory


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
        db=db,
        scope_reader=ScopedNumberPoolReader(db=db),
        schema_manager=registry.schema,
        upserter=upserter,
        range_store_factory=range_store_factory,
    ).run()


async def ranges_of(db: InfrahubDatabase, pool_id: str) -> list[tuple[int | None, int | None, int | None]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    return [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]


async def range_ids_of(db: InfrahubDatabase, pool_id: str) -> list[str]:
    return [item.get_id() for item in await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)]


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


async def test_declaration_without_range_gives_one_open_range_a_reload_leaves_alone(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """An attribute declaring neither spelling gets one range open at both ends, and loading it again writes nothing."""
    pool_id = await provision_pool(db=db, branch=default_branch, parameters=NumberPoolParameters())
    assert await ranges_of(db=db, pool_id=pool_id) == [(None, None, None)]
    assert await shorthand_of(db=db, pool_id=pool_id) == (None, None)
    range_ids = await range_ids_of(db=db, pool_id=pool_id)

    recording_factory = NumberPoolRepositoryRecordingWritesFactory()
    await redeclare(
        db=db, branch=default_branch, parameters=NumberPoolParameters(), range_store_factory=recording_factory
    )

    assert recording_factory.get_writes() == []
    assert await range_ids_of(db=db, pool_id=pool_id) == range_ids
    assert await ranges_of(db=db, pool_id=pool_id) == [(None, None, None)]


async def test_empty_range_list_removes_the_open_range(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Declaring an empty range list after declaring nothing removes the open range the pool held."""
    pool_id = await provision_pool(db=db, branch=default_branch, parameters=NumberPoolParameters())

    await redeclare(db=db, branch=default_branch, parameters=NumberPoolParameters(ranges=[]))

    assert await ranges_of(db=db, pool_id=pool_id) == []
    assert await shorthand_of(db=db, pool_id=pool_id) == (None, None)


async def test_declaration_without_range_keeps_the_previously_declared_ranges(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A later declaration using neither spelling keeps the ranges an earlier declaration set."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    range_ids = await range_ids_of(db=db, pool_id=pool_id)

    await redeclare(db=db, branch=default_branch, parameters=NumberPoolParameters())

    assert await range_ids_of(db=db, pool_id=pool_id) == range_ids
    assert await ranges_of(db=db, pool_id=pool_id) == [(1, 100, None)]
    assert await shorthand_of(db=db, pool_id=pool_id) == (1, 100)


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
