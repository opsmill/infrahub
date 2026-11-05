import re

import pytest

from infrahub.core.attribute import ListAttributeOptional, String
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipDirection
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import NumberAttributeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import DivisionExhaustedError, PoolExhaustedError
from infrahub.pools.number_pool_number_picker import NumberPoolNumberPicker
from infrahub.pools.number_ranges import PoolRange
from infrahub.pools.scope import Division, DivisionElementPath
from tests.unit.pools.helpers import InMemoryNumberPoolNumbers

BRANCH = Branch(name="main")
UNIQUE_ATTRIBUTE = NumberAttributeSchema(name="ticket_id", kind="Number", unique=True)
SITE_PEER_ID = "1866fa8c-0000-4000-8000-000000000003"
SITE_ROLE_DIVISION = Division(
    elements=(
        DivisionElementPath(name="scope_ticket__site", relationship_direction=RelationshipDirection.OUTBOUND),
        DivisionElementPath(name="role"),
    ),
    values=(SITE_PEER_ID, "leaf"),
)


@pytest.fixture
def pool() -> CoreNumberPool:
    name_schema = AttributeSchema(name="name", kind="Text")
    schema = NodeSchema(name="NumberPool", namespace="Core", attributes=[name_schema])
    pool = CoreNumberPool(schema=schema, branch=BRANCH, at=Timestamp())
    pool.id = "pool-1"
    name = String(name="name", schema=name_schema, branch=BRANCH, at=Timestamp(), node=pool, data="tickets")
    setattr(pool, "name", name)  # noqa: B010
    return pool


@pytest.fixture
def site_role_scoped_pool(pool: CoreNumberPool) -> CoreNumberPool:
    scope_schema = AttributeSchema(name="allocation_scope", kind="List", optional=True)
    scope = ListAttributeOptional(
        name="allocation_scope",
        schema=scope_schema,
        branch=BRANCH,
        at=Timestamp(),
        node=pool,
        data={
            "value": [
                {"id": "17d0a4c2-0000-4000-8000-000000000001", "name": "site"},
                {"id": "3b1f90ee-0000-4000-8000-000000000002", "name": "role"},
            ]
        },
    )
    setattr(pool, scope.name, scope)
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
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=3)], accounted={1, 2, 3})

    with pytest.raises(PoolExhaustedError) as exc_info:
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE
        )
    assert exc_info.value.message == "Pool tickets (pool-1) has no free number left in its ranges."
    assert type(exc_info.value) is PoolExhaustedError


async def test_a_full_division_is_exhausted_naming_the_division(site_role_scoped_pool: CoreNumberPool) -> None:
    numbers = InMemoryNumberPoolNumbers(
        ranges=[PoolRange(id="first", start=1, end=3), PoolRange(id="second", start=10, end=11)],
        accounted={1, 2, 3, 10, 11},
    )
    expected = (
        "Pool tickets (pool-1) has no free number left in its ranges for "
        "site '1866fa8c-0000-4000-8000-000000000003', role 'leaf'."
    )

    with pytest.raises(DivisionExhaustedError, match=f"^{re.escape(expected)}$") as exc_info:
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=site_role_scoped_pool, branch=BRANCH, attribute=UNIQUE_ATTRIBUTE, division=SITE_ROLE_DIVISION
        )
    assert exc_info.value.message == expected
    assert exc_info.value.division == SITE_ROLE_DIVISION
    assert exc_info.value.space_size == 5
    assert exc_info.value.HTTP_CODE == 409


async def test_a_division_whose_ranges_the_attribute_rejects_keeps_the_pool_wide_text(
    site_role_scoped_pool: CoreNumberPool,
) -> None:
    numbers = InMemoryNumberPoolNumbers(ranges=[PoolRange(id="only", start=1, end=10)])
    attribute = NumberAttributeSchema(
        name="ticket_id", kind="Number", unique=True, parameters=NumberAttributeParameters(min_value=20)
    )

    with pytest.raises(
        PoolExhaustedError,
        match=r"^Pool tickets \(pool-1\) has no number the attribute accepts in its ranges\.$",
    ) as exc_info:
        await NumberPoolNumberPicker(number_reader=numbers).next_number(
            pool=site_role_scoped_pool, branch=BRANCH, attribute=attribute, division=SITE_ROLE_DIVISION
        )
    assert type(exc_info.value) is PoolExhaustedError
    assert numbers.free_lookups == []


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
