import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PoolExhaustedError
from infrahub.pools.number_pool_allocator import NumberPoolAllocator
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from tests.helpers.number_pool import (
    add_pool_range,
    create_range_only_pool,
    create_ticket,
    shorthand_mirror,
    ticket_schema_with_parameters,
)
from tests.helpers.schema import TICKET, load_schema


async def test_allocation_from_a_pool_holding_several_ranges_starts_at_the_lowest_range(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool whose shorthand is null because it holds several ranges allocates from those ranges."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=100, end=200)
    await add_pool_range(db=db, pool=pool, start=300, end=400)
    await shorthand_mirror(db=db).sync(pool=pool)
    assert (pool.start_range.value, pool.end_range.value) == (None, None)

    assert await _next_number(db=db, branch=default_branch, pool=pool) == 100


async def test_allocation_from_a_pool_without_range_reports_the_pool_exhausted(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="empty-pool", node="TestingTicket", node_attribute="ticket_id")
    await pool.save(db=db)

    with pytest.raises(PoolExhaustedError) as exc_info:
        await _next_number(db=db, branch=default_branch, pool=pool)

    assert exc_info.value.message == (
        f"Pool empty-pool ({pool.get_id()}) has no number the attribute accepts in its ranges."
    )


async def _create_hand_set_ticket(db: InfrahubDatabase, kind: str, value: int) -> None:
    ticket = await Node.init(db=db, schema=kind)
    await ticket.new(db=db, title=f"manual {value}", ticket_id=value)
    await ticket.save(db=db)


async def _next_number(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool, kind: str = TICKET.kind) -> int:
    """Return the number the pool would hand out next, without reserving it."""
    attribute = registry.schema.get_node_schema(name=kind, branch=branch).get_attribute(name="ticket_id")
    allocator = NumberPoolAllocator(numbers=NumberPoolRepository(db=db))
    return await allocator.next_number(pool=pool, branch=branch, attribute=attribute)


@pytest.fixture
async def weighted_pool(db: InfrahubDatabase, ticket_schema: None) -> CoreNumberPool:
    """A pool holding a heavier 10-12 range and a 15-17 range, with 13-14 left out between them."""
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=15, end=17)
    await add_pool_range(db=db, pool=pool, start=10, end=12, weight=10)
    return pool


async def test_the_heavier_range_is_drained_first_in_ascending_order(
    db: InfrahubDatabase, default_branch: Branch, weighted_pool: CoreNumberPool
) -> None:
    allocated = [await create_ticket(db=db, kind=TICKET.kind, pool=weighted_pool) for _ in range(3)]

    assert allocated == [10, 11, 12]


async def test_allocation_moves_to_the_next_range_across_the_gap(
    db: InfrahubDatabase, weighted_pool: CoreNumberPool
) -> None:
    for _ in range(3):
        await create_ticket(db=db, kind=TICKET.kind, pool=weighted_pool)

    assert await create_ticket(db=db, kind=TICKET.kind, pool=weighted_pool) == 15


async def test_the_pool_is_full_only_once_every_range_is_drained(
    db: InfrahubDatabase, default_branch: Branch, weighted_pool: CoreNumberPool
) -> None:
    allocated = [await create_ticket(db=db, kind=TICKET.kind, pool=weighted_pool) for _ in range(6)]
    assert allocated == [10, 11, 12, 15, 16, 17]

    with pytest.raises(PoolExhaustedError):
        await _next_number(db=db, branch=default_branch, pool=weighted_pool)


@pytest.mark.parametrize("weight", [None, 5], ids=["no-weight", "equal-weight"])
async def test_ranges_of_equal_weight_are_drained_lowest_start_first(
    db: InfrahubDatabase, ticket_schema: None, weight: int | None
) -> None:
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=50, end=51, weight=weight)
    await add_pool_range(db=db, pool=pool, start=10, end=11, weight=weight)

    allocated = [await create_ticket(db=db, kind=TICKET.kind, pool=pool) for _ in range(4)]

    assert allocated == [10, 11, 50, 51]


async def test_raising_a_range_weight_redirects_the_next_allocation(db: InfrahubDatabase, ticket_schema: None) -> None:
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)
    upper = await add_pool_range(db=db, pool=pool, start=20, end=30)
    assert [await create_ticket(db=db, kind=TICKET.kind, pool=pool) for _ in range(2)] == [1, 2]

    upper.get_attribute("allocation_weight").value = 5
    await upper.save(db=db)

    assert await create_ticket(db=db, kind=TICKET.kind, pool=pool) == 20


async def test_excluded_values_inside_a_range_are_skipped(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    schema = ticket_schema_with_parameters(NumberAttributeParameters(excluded_values="102,105-107"))
    await load_schema(db=db, schema=SchemaRoot(nodes=[schema]))
    await initialize_registry(db=db)
    pool = await create_range_only_pool(db=db, kind=schema.kind)
    await add_pool_range(db=db, pool=pool, start=100, end=120)

    allocated = [await create_ticket(db=db, kind=schema.kind, pool=pool) for _ in range(5)]

    assert allocated == [100, 101, 103, 104, 108]


async def test_min_and_max_values_clip_the_ranges(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A range clipped to nothing holds no allocatable number and counts as exhausted."""
    schema = ticket_schema_with_parameters(NumberAttributeParameters(min_value=15, max_value=50))
    await load_schema(db=db, schema=SchemaRoot(nodes=[schema]))
    await initialize_registry(db=db)
    pool = await create_range_only_pool(db=db, kind=schema.kind)
    await add_pool_range(db=db, pool=pool, start=10, end=20, weight=10)
    await add_pool_range(db=db, pool=pool, start=60, end=80, weight=20)

    allocated = [await create_ticket(db=db, kind=schema.kind, pool=pool) for _ in range(6)]
    assert allocated == [15, 16, 17, 18, 19, 20]

    with pytest.raises(PoolExhaustedError):
        await _next_number(db=db, branch=default_branch, pool=pool, kind=schema.kind)


async def test_hand_set_values_are_skipped_in_every_range(
    db: InfrahubDatabase, default_branch: Branch, ticket_schema: None
) -> None:
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=5, weight=10)
    await add_pool_range(db=db, pool=pool, start=10, end=15)
    for value in (1, 3, 7, 10, 11):
        await _create_hand_set_ticket(db=db, kind=TICKET.kind, value=value)

    repository = NumberPoolRepository(db=db)
    space = EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=pool.get_id()), domain=NumberDomain())
    assert await repository.get_taken(pool=pool, branch=default_branch, space=space) == {1, 3, 10, 11}

    allocated = [await create_ticket(db=db, kind=TICKET.kind, pool=pool) for _ in range(4)]

    assert allocated == [2, 4, 5, 12]
