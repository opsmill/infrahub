import pytest

from infrahub.core.attribute import String
from infrahub.core.branch import Branch
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import NumberAttributeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import PoolExhaustedError
from infrahub.pools.number_pool_number_picker import NumberPoolNumberPicker
from infrahub.pools.number_ranges import PoolRange
from tests.unit.pools.helpers import InMemoryNumberPoolNumbers

BRANCH = Branch(name="main")
UNIQUE_ATTRIBUTE = NumberAttributeSchema(name="ticket_id", kind="Number", unique=True)
SHARED_ATTRIBUTE = NumberAttributeSchema(name="ticket_id", kind="Number", unique=False)


@pytest.fixture
def pool() -> CoreNumberPool:
    name_schema = AttributeSchema(name="name", kind="Text")
    schema = NodeSchema(name="NumberPool", namespace="Core", attributes=[name_schema])
    pool = CoreNumberPool(schema=schema, branch=BRANCH, at=Timestamp())
    pool.id = "pool-1"
    name = String(name="name", schema=name_schema, branch=BRANCH, at=Timestamp(), node=pool, data="tickets")
    setattr(pool, "name", name)  # noqa: B010
    return pool


async def test_the_heaviest_range_is_drained_before_the_lowest_one(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(
        ranges=[PoolRange(id="low", start=100, end=200), PoolRange(id="heavy", start=205, end=300, weight=10)],
        accounted={205, 206},
    )

    assert (
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
        == 207
    )


async def test_a_full_range_hands_over_to_the_next_one(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(
        ranges=[PoolRange(id="first", start=1, end=3), PoolRange(id="second", start=10, end=12)], accounted={1, 2, 3}
    )

    assert (
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
        == 10
    )
    assert numbers.free_lookups == [(1, 3), (10, 12)]


async def test_a_run_of_values_held_by_hand_costs_a_single_free_lookup(pool: CoreNumberPool) -> None:
    """Values the target holds outside the pool are stepped over in memory, not one lookup per value."""
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=10)], taken={1, 2, 3})

    assert (
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
        == 4
    )
    assert numbers.free_lookups == [(4, 10)]


async def test_a_free_number_the_target_holds_by_hand_is_skipped(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=10)], accounted={1}, taken={2})

    assert (
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
        == 3
    )
    assert numbers.free_lookups == [(1, 10), (3, 10)]


async def test_a_shared_attribute_ignores_values_held_by_hand(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=10)], taken={1, 2, 3})

    assert (
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=SHARED_ATTRIBUTE
        )
        == 1
    )


async def test_the_numbers_the_attribute_accepts_clip_the_ranges(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=10)])
    attribute = NumberAttributeSchema(
        name="ticket_id",
        kind="Number",
        unique=True,
        parameters=NumberAttributeParameters(min_value=5, max_value=20, excluded_values="5-6"),
    )

    assert (
        await NumberPoolNumberPicker(number_reader=numbers).next_number(pool=pool, branch=BRANCH, attribute=attribute)
        == 7
    )
    assert numbers.free_lookups == [(7, 10)]


async def test_a_pool_without_a_free_number_is_exhausted(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=3)], accounted={1, 2}, taken={3})

    with pytest.raises(PoolExhaustedError) as exc_info:
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
    assert exc_info.value.message == "Pool tickets (pool-1) has no free number left in its ranges."


async def test_a_pool_without_a_range_is_exhausted(pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers()

    with pytest.raises(PoolExhaustedError) as exc_info:
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
    assert exc_info.value.message == "Pool tickets (pool-1) has no number the attribute accepts in its ranges."
    assert numbers.free_lookups == []


async def test_a_pool_whose_ranges_the_attribute_rejects_is_exhausted(pool: CoreNumberPool) -> None:
    """A range clipped to nothing is told apart from a drained one, before any lookup."""
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=10)])
    attribute = NumberAttributeSchema(
        name="ticket_id", kind="Number", unique=True, parameters=NumberAttributeParameters(min_value=20)
    )

    with pytest.raises(PoolExhaustedError) as exc_info:
        await NumberPoolNumberPicker(number_reader=numbers).next_number(pool=pool, branch=BRANCH, attribute=attribute)
    assert exc_info.value.message == "Pool tickets (pool-1) has no number the attribute accepts in its ranges."
    assert numbers.free_lookups == []
