from copy import deepcopy
from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    CREATE_NUMBER_POOL_WITH_BOUNDS,
    CREATE_RANGE,
    UPDATE_POOL_RANGES,
    UPDATE_POOL_SHORTHAND,
    UPDATE_RANGE,
    create_pool,
    execute,
    range_details,
    ticket_pool_input,
)

MIN_VALUE = 10
MAX_VALUE = 100
BELOW_MIN_ERROR = "Range 5-20 starts below the attribute's min_value (10)"
ABOVE_MAX_ERROR = "Range 50-150 ends above the attribute's max_value (100)"


@dataclass
class OutOfBoundsCase:
    name: str
    start: int
    end: int
    expected_error: str


OUT_OF_BOUNDS_CASES: list[OutOfBoundsCase] = [
    OutOfBoundsCase(name="below_min_value", start=5, end=20, expected_error=BELOW_MIN_ERROR),
    OutOfBoundsCase(name="above_max_value", start=50, end=150, expected_error=ABOVE_MAX_ERROR),
]


class TestNumberPoolRangeAttributeBounds:
    """Every way of writing a range refuses one reaching outside the attribute's min_value / max_value.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def bounded_ticket_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        ticket = deepcopy(TICKET)
        ticket.get_attribute(name="ticket_id").parameters = NumberAttributeParameters(
            min_value=MIN_VALUE, max_value=MAX_VALUE
        )
        await load_schema(db=db, schema=SchemaRoot(nodes=[ticket]))
        default_branch_scope_class.update_schema_hash()

    @pytest.mark.parametrize("case", OUT_OF_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_pool_creation_with_ranges_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        bounded_ticket_schema: None,
        case: OutOfBoundsCase,
    ) -> None:
        pools_before = await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={
                "data": ticket_pool_input(
                    name=f"out-of-bounds-create-{case.name}",
                    bounds={"ranges": [{"start": case.start, "end": case.end}]},
                )
            },
        )

        assert [error.message for error in result.errors or []] == [case.expected_error]
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
            == pools_before
        )

    @pytest.mark.parametrize("case", OUT_OF_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_pool_update_with_ranges_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        bounded_ticket_schema: None,
        case: OutOfBoundsCase,
    ) -> None:
        pool_id = await self._create_pool(db=db, branch=default_branch_scope_class, name=f"ranges-{case.name}")
        ranges_before = await range_details(db=db, pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": pool_id, "ranges": [{"start": case.start, "end": case.end}]},
        )

        assert [error.message for error in result.errors or []] == [case.expected_error]
        assert await range_details(db=db, pool_id=pool_id) == ranges_before

    @pytest.mark.parametrize("case", OUT_OF_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_pool_update_of_the_shorthand_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        bounded_ticket_schema: None,
        case: OutOfBoundsCase,
    ) -> None:
        pool_id = await self._create_pool(db=db, branch=default_branch_scope_class, name=f"shorthand-{case.name}")
        ranges_before = await range_details(db=db, pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_POOL_SHORTHAND,
            variables={"pool_id": pool_id, "start": case.start, "end": case.end},
        )

        assert [error.message for error in result.errors or []] == [case.expected_error]
        assert await range_details(db=db, pool_id=pool_id) == ranges_before

    @pytest.mark.parametrize("case", OUT_OF_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_range_creation_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        bounded_ticket_schema: None,
        case: OutOfBoundsCase,
    ) -> None:
        pool_id = await self._create_pool(db=db, branch=default_branch_scope_class, name=f"range-create-{case.name}")
        ranges_before = await range_details(db=db, pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": pool_id, "start": case.start, "end": case.end},
        )

        assert [error.message for error in result.errors or []] == [case.expected_error]
        assert await range_details(db=db, pool_id=pool_id) == ranges_before

    @pytest.mark.parametrize("case", OUT_OF_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_range_update_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        bounded_ticket_schema: None,
        case: OutOfBoundsCase,
    ) -> None:
        pool_id = await self._create_pool(db=db, branch=default_branch_scope_class, name=f"range-update-{case.name}")
        ranges_before = await range_details(db=db, pool_id=pool_id)
        (pool_range,) = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": pool_range.get_id(), "start": case.start, "end": case.end},
        )

        assert [error.message for error in result.errors or []] == [case.expected_error]
        assert await range_details(db=db, pool_id=pool_id) == ranges_before

    async def test_ranges_inside_the_attribute_bounds_are_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, bounded_ticket_schema: None
    ) -> None:
        pool_id = await self._create_pool(db=db, branch=default_branch_scope_class, name="inside-bounds")

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_POOL_RANGES,
            variables={
                "pool_id": pool_id,
                "ranges": [{"start": MIN_VALUE, "end": 20}, {"start": 90, "end": MAX_VALUE}],
            },
        )

        assert not result.errors
        assert [(start, end) for _, start, end, _ in await range_details(db=db, pool_id=pool_id)] == [
            (MIN_VALUE, 20),
            (90, MAX_VALUE),
        ]

    async def _create_pool(self, db: InfrahubDatabase, branch: Branch, name: str) -> str:
        return await create_pool(
            db=db, branch=branch, name=f"bounded-pool-{name}", bounds={"ranges": [{"start": 30, "end": 40}]}
        )
