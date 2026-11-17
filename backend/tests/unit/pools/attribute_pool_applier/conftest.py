from __future__ import annotations

import pytest

from infrahub.pools.attribute_pool_applier import AttributePoolApplier
from infrahub.pools.intent import FromPoolIntentResolver
from infrahub.pools.number_ranges import PoolRange
from tests.unit.pools.attribute_pool_applier.helpers import (
    OTHER_ATTRIBUTE_POOL_ID,
    OTHER_POOL_ID,
    POOL_ID,
    InMemoryAttributeBranchValues,
    InMemoryNumberPoolFinder,
    InMemoryPoolRangeReader,
    RecordingNumberAllocator,
    UnscopedDivisionReader,
)
from tests.unit.pools.helpers import InMemoryNumberPool


@pytest.fixture
def finder() -> InMemoryNumberPoolFinder:
    return InMemoryNumberPoolFinder(
        pools=[
            InMemoryNumberPool(id=POOL_ID, name="tickets"),
            InMemoryNumberPool(id=OTHER_POOL_ID, name="other-tickets"),
            InMemoryNumberPool(id=OTHER_ATTRIBUTE_POOL_ID, name="titles", node_attribute="title"),
        ]
    )


@pytest.fixture
def allocator() -> RecordingNumberAllocator:
    return RecordingNumberAllocator()


@pytest.fixture
def range_reader() -> InMemoryPoolRangeReader:
    return InMemoryPoolRangeReader(
        ranges_by_pool_id={
            POOL_ID: [PoolRange(id="tickets-range", start=1, end=100)],
            OTHER_POOL_ID: [PoolRange(id="other-tickets-range", start=1, end=100)],
            OTHER_ATTRIBUTE_POOL_ID: [PoolRange(id="titles-range", start=1, end=100)],
        }
    )


@pytest.fixture
def branch_values() -> InMemoryAttributeBranchValues:
    return InMemoryAttributeBranchValues()


@pytest.fixture
def applier(
    finder: InMemoryNumberPoolFinder,
    allocator: RecordingNumberAllocator,
    range_reader: InMemoryPoolRangeReader,
    branch_values: InMemoryAttributeBranchValues,
) -> AttributePoolApplier:
    return AttributePoolApplier(
        pool_finder=finder,
        number_allocator=allocator,
        intent_resolver=FromPoolIntentResolver(),
        division_reader=UnscopedDivisionReader(),
        range_reader=range_reader,
        branch_values_reader=branch_values,
    )
