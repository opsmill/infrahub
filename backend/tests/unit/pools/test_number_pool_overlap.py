from dataclasses import dataclass, field

import pytest

from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import NumberAttributeSchema
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_overlap import NumberPoolOverlapChecker, PoolRangeSet
from infrahub.pools.number_pool_range_validation import NumberRangeBounds

KIND = "TestingTicket"
UNIQUE_ATTRIBUTE = NumberAttributeSchema(name="ticket_id", kind="Number", unique=True)
SHARED_ATTRIBUTE = NumberAttributeSchema(name="ticket_id", kind="Number", unique=False)


@dataclass
class InMemoryAttributePools:
    pools: list[PoolRangeSet]
    reads: list[tuple[str, str]] = field(default_factory=list)

    async def get_attribute_pool_ranges(self, kind: str, attribute_name: str) -> list[PoolRangeSet]:
        self.reads.append((kind, attribute_name))
        return self.pools


def pool_a(*ranges: NumberRangeBounds) -> PoolRangeSet:
    return PoolRangeSet(pool_id="pool-a", pool_name="tickets-a", ranges=list(ranges))


async def test_a_range_overlapping_another_pool_on_a_unique_attribute_is_refused() -> None:
    reader = InMemoryAttributePools(pools=[pool_a(NumberRangeBounds(start=1, end=10))])

    with pytest.raises(ValidationError) as exc_info:
        await NumberPoolOverlapChecker(pool_reader=reader).check(
            pool_id="pool-b",
            pool_name="tickets-b",
            kind=KIND,
            attribute=UNIQUE_ATTRIBUTE,
            ranges=[NumberRangeBounds(start=20, end=30), NumberRangeBounds(start=5, end=15)],
        )

    assert exc_info.value.message == (
        "The 'tickets-b' pool cannot share numbers with another pool on the unique attribute 'ticket_id': "
        "5 - 15 overlaps 1 - 10 of the 'tickets-a' pool. Choose ranges that no other pool on 'ticket_id' uses."
    )
    assert reader.reads == [(KIND, "ticket_id")]


async def test_an_open_range_reads_its_bounds_through_the_attribute() -> None:
    reader = InMemoryAttributePools(pools=[pool_a(NumberRangeBounds(start=90, end=None))])
    attribute = NumberAttributeSchema(
        name="ticket_id", kind="Number", unique=True, parameters=NumberAttributeParameters(min_value=1, max_value=100)
    )

    with pytest.raises(ValidationError) as exc_info:
        await NumberPoolOverlapChecker(pool_reader=reader).check(
            pool_id="pool-b",
            pool_name="tickets-b",
            kind=KIND,
            attribute=attribute,
            ranges=[NumberRangeBounds(start=None, end=None)],
        )

    assert exc_info.value.message == (
        "The 'tickets-b' pool cannot share numbers with another pool on the unique attribute 'ticket_id': "
        "1 - 100 overlaps 90 - 100 of the 'tickets-a' pool. Choose ranges that no other pool on 'ticket_id' uses."
    )


async def test_adjacent_ranges_of_two_pools_are_accepted() -> None:
    reader = InMemoryAttributePools(pools=[pool_a(NumberRangeBounds(start=1, end=10))])

    await NumberPoolOverlapChecker(pool_reader=reader).check(
        pool_id="pool-b",
        pool_name="tickets-b",
        kind=KIND,
        attribute=UNIQUE_ATTRIBUTE,
        ranges=[NumberRangeBounds(start=11, end=20)],
    )

    assert reader.reads == [(KIND, "ticket_id")]


async def test_the_pool_s_own_stored_ranges_are_not_an_overlap() -> None:
    reader = InMemoryAttributePools(
        pools=[PoolRangeSet(pool_id="pool-b", pool_name="tickets-b", ranges=[NumberRangeBounds(start=1, end=10)])]
    )

    await NumberPoolOverlapChecker(pool_reader=reader).check(
        pool_id="pool-b",
        pool_name="tickets-b",
        kind=KIND,
        attribute=UNIQUE_ATTRIBUTE,
        ranges=[NumberRangeBounds(start=5, end=15)],
    )

    assert reader.reads == [(KIND, "ticket_id")]


async def test_pools_on_an_attribute_that_is_not_unique_may_overlap() -> None:
    reader = InMemoryAttributePools(pools=[pool_a(NumberRangeBounds(start=1, end=10))])

    await NumberPoolOverlapChecker(pool_reader=reader).check(
        pool_id="pool-b",
        pool_name="tickets-b",
        kind=KIND,
        attribute=SHARED_ATTRIBUTE,
        ranges=[NumberRangeBounds(start=1, end=10)],
    )

    assert reader.reads == []
