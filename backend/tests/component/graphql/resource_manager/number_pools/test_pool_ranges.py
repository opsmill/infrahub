from dataclasses import dataclass
from typing import Any

import pytest
from graphql import ExecutionResult

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import add_pool_range, pool_used_numbers
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    CREATE_RANGE,
    DELETE_RANGE,
    UPDATE_POOL_RANGES,
    UPDATE_POOL_SHORTHAND,
    UPDATE_RANGE,
    UPSERT_NEW_RANGE,
    UPSERT_RANGE,
    load_pool,
)

DELETE_POOL = """
mutation DeletePool($pool_id: String!) {
    CoreNumberPoolDelete(data: { id: $pool_id }) {
        ok
    }
}
"""

MOVE_RANGE = """
mutation MoveRange($range_id: String!, $pool_id: String!) {
    CoreNumberPoolRangeUpdate(data: { id: $range_id, pool: { id: $pool_id } }) {
        ok
    }
}
"""

QUERY_POOL_WITH_RANGES = """
query PoolWithRanges($pool_id: ID!) {
    CoreNumberPool(ids: [$pool_id]) {
        edges {
            node {
                id
                start_range { value }
                end_range { value }
                ranges {
                    count
                    edges {
                        node {
                            id
                            display_label
                            start { value }
                            end { value }
                        }
                    }
                }
            }
        }
    }
}
"""

POOL_UTILIZATION = """
query PoolUtilization($pool_id: String!) {
    InfrahubResourcePoolUtilization(pool_id: $pool_id) {
        count
        utilization
        edges {
            node {
                display_label
                utilization
            }
        }
    }
}
"""

CREATE_POOL_WITHOUT_BOUNDS = """
mutation CreatePool {
    CoreNumberPoolCreate(data: {
        name: { value: "mirrored-pool" }
        node: { value: "TestingTicket" }
        node_attribute: { value: "ticket_id" }
    }) {
        object { id }
    }
}
"""


async def _create_pool(db: InfrahubDatabase, name: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=100)
    await pool.save(db=db)
    return pool


async def _create_pool_with_range(db: InfrahubDatabase, name: str, start: int, end: int) -> tuple[CoreNumberPool, Node]:
    """Build a pool whose shorthand matches its single range, so it allocates from that range."""
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node="TestingTicket", node_attribute="ticket_id", start_range=start, end_range=end)
    await pool.save(db=db)
    pool_range = await add_pool_range(db=db, pool=pool, start=start, end=end)
    return pool, pool_range


async def _execute(db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]) -> ExecutionResult:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def _allocate_ticket(db: InfrahubDatabase, pool: CoreNumberPool, title: str) -> None:
    ticket = await Node.init(db=db, schema=TICKET.kind)
    await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool.get_id()}})
    await ticket.save(db=db)


async def _ticket_ids(db: InfrahubDatabase, branch: Branch, titles: list[str]) -> dict[str, int]:
    tickets = await NodeManager.query(db=db, schema=TICKET.kind, branch=branch, filters={"title__values": titles})
    return {ticket.get_attribute("title").value: ticket.get_attribute("ticket_id").value for ticket in tickets}


async def _range_bounds(db: InfrahubDatabase, pool: CoreNumberPool) -> list[tuple[int | None, int | None]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
    return [(pool_range.start.value, pool_range.end.value) for pool_range in ranges]


async def _create_range(
    db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool, start: int, end: int, weight: int | None = None
) -> str:
    result = await _execute(
        db=db,
        branch=branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool.get_id(), "start": start, "end": end, "weight": weight},
    )
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPoolRangeCreate"]["object"]["id"]


async def _utilization(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool) -> dict[str, Any]:
    result = await _execute(db=db, branch=branch, source=POOL_UTILIZATION, variables={"pool_id": pool.get_id()})
    assert not result.errors
    assert result.data
    return result.data["InfrahubResourcePoolUtilization"]


def _percent(used: int, size: int) -> float:
    return used / size * 100


async def _shorthand_and_ranges(
    db: InfrahubDatabase, pool_id: str
) -> tuple[tuple[int | None, int | None], list[tuple[int | None, int | None]]]:
    pool = await load_pool(db=db, pool_id=pool_id)
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    return (
        (pool.start_range.value, pool.end_range.value),
        [(pool_range.start.value, pool_range.end.value) for pool_range in ranges],
    )


@dataclass(frozen=True)
class TwoRangePool:
    pool: CoreNumberPool
    low: Node
    high: Node


@dataclass(frozen=True, kw_only=True)
class OpenBoundCase:
    name: str
    start: int | None
    end: int | None


ONE_BOUND_CASES = [
    OpenBoundCase(name="start_only", start=50, end=None),
    OpenBoundCase(name="end_only", start=None, end=50),
]

REMOVED_BOUND_CASES = [
    OpenBoundCase(name="start_removed", start=None, end=200),
    OpenBoundCase(name="end_removed", start=100, end=None),
]


@dataclass(frozen=True, kw_only=True)
class OpenOverlapCase:
    name: str
    start: int | None
    end: int | None
    label: str
    overlaps_the_high_range: bool


OPEN_OVERLAP_CASES = [
    OpenOverlapCase(
        name="open_end_runs_over_every_higher_range",
        start=150,
        end=None,
        label="150 - MAX",
        overlaps_the_high_range=True,
    ),
    OpenOverlapCase(
        name="open_start_runs_into_the_lowest_range",
        start=None,
        end=100,
        label="1 - 100",
        overlaps_the_high_range=False,
    ),
]


class TestNumberPoolRangeMutations:
    """The schema is loaded once for the class, and every test creates pools under names of its own.

    `ticket_id` is unique, so the tests that hand out numbers draw them from ranges no other test hands out from.
    """

    @pytest.fixture(scope="class")
    async def ticket_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        default_branch_scope_class.update_schema_hash()
        await initialize_registry(db=db)

    @pytest.fixture(scope="class")
    async def two_range_pool(self, db: InfrahubDatabase, ticket_schema: None) -> TwoRangePool:
        """A pool holding 100-200 and 300-400, shared by the tests that refuse a range write and so leave it as it is."""
        pool, low = await _create_pool_with_range(db=db, name="two-range-pool", start=100, end=200)
        high = await add_pool_range(db=db, pool=pool, start=300, end=400)
        return TwoRangePool(pool=pool, low=low, high=high)

    async def test_range_created_through_mutation_is_listed_under_its_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool = await _create_pool(db=db, name="listed-range-pool")

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": pool.get_id(), "start": 10, "end": 20, "weight": 5},
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolRangeCreate"]
        assert created["ok"]
        assert created["object"]["start"]["value"] == 10
        assert created["object"]["end"]["value"] == 20
        assert created["object"]["allocation_weight"]["value"] == 5

        range_node = await NodeManager.get_one(id=created["object"]["id"], db=db, branch=default_branch_scope_class)
        assert range_node is not None
        assert range_node.get_kind() == InfrahubKind.NUMBERPOOLRANGE
        assert (range_node.start.value, range_node.end.value) == (10, 20)
        assert range_node.allocation_weight.value == 5
        assert (await range_node.pool.get_peer(db=db)).get_id() == pool.get_id()

        read = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=QUERY_POOL_WITH_RANGES,
            variables={"pool_id": pool.get_id()},
        )

        assert not read.errors
        assert read.data
        node = read.data["CoreNumberPool"]["edges"][0]["node"]
        assert node["ranges"]["count"] == 1
        assert node["ranges"]["edges"][0]["node"]["start"]["value"] == 10
        assert node["ranges"]["edges"][0]["node"]["end"]["value"] == 20
        assert node["start_range"]["value"] == 10
        assert node["end_range"]["value"] == 20

    async def test_pool_accepts_several_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool = await _create_pool(db=db, name="several-ranges-pool")

        for start, end in ((30, 40), (10, 20)):
            result = await _execute(
                db=db,
                branch=default_branch_scope_class,
                source=CREATE_RANGE,
                variables={"pool_id": pool.get_id(), "start": start, "end": end, "weight": None},
            )
            assert not result.errors
            assert result.data
            assert result.data["CoreNumberPoolRangeCreate"]["ok"]
            assert result.data["CoreNumberPoolRangeCreate"]["object"]["allocation_weight"]["value"] is None

        read = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=QUERY_POOL_WITH_RANGES,
            variables={"pool_id": pool.get_id()},
        )

        assert not read.errors
        assert read.data
        node = read.data["CoreNumberPool"]["edges"][0]["node"]
        assert node["ranges"]["count"] == 2
        bounds = [(edge["node"]["start"]["value"], edge["node"]["end"]["value"]) for edge in node["ranges"]["edges"]]
        assert bounds == [(10, 20), (30, 40)]

    async def test_range_display_label_is_its_bounds(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool = await _create_pool(db=db, name="labelled-range-pool")
        await _create_range(db=db, branch=default_branch_scope_class, pool=pool, start=10, end=20)

        read = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=QUERY_POOL_WITH_RANGES,
            variables={"pool_id": pool.get_id()},
        )

        assert not read.errors
        assert read.data
        node = read.data["CoreNumberPool"]["edges"][0]["node"]
        assert [edge["node"]["display_label"] for edge in node["ranges"]["edges"]] == ["10 - 20"]

    async def test_deleting_a_pool_deletes_its_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool = await _create_pool(db=db, name="deleted-pool")
        range_ids = [
            await _create_range(db=db, branch=default_branch_scope_class, pool=pool, start=10, end=20),
            await _create_range(db=db, branch=default_branch_scope_class, pool=pool, start=30, end=40),
        ]

        deleted = await _execute(
            db=db, branch=default_branch_scope_class, source=DELETE_POOL, variables={"pool_id": pool.get_id()}
        )

        assert not deleted.errors
        assert deleted.data
        assert deleted.data["CoreNumberPoolDelete"]["ok"]

        assert await NodeManager.get_one(id=pool.get_id(), db=db, branch=default_branch_scope_class) is None
        remaining = await NodeManager.get_many(ids=range_ids, db=db, branch=default_branch_scope_class)
        assert remaining == {}

    async def test_adding_a_range_to_a_pool_in_use_leaves_allocated_values_untouched(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool, _ = await _create_pool_with_range(db=db, name="in-use-pool", start=100, end=200)
        titles = ["in-use-first", "in-use-second"]
        for title in titles:
            await _allocate_ticket(db=db, pool=pool, title=title)
        assert await _ticket_ids(db=db, branch=default_branch_scope_class, titles=titles) == {
            "in-use-first": 100,
            "in-use-second": 101,
        }

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": pool.get_id(), "start": 205, "end": 300, "weight": None},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolRangeCreate"]["ok"]
        assert await _range_bounds(db=db, pool=pool) == [(100, 200), (205, 300)]
        assert await _ticket_ids(db=db, branch=default_branch_scope_class, titles=titles) == {
            "in-use-first": 100,
            "in-use-second": 101,
        }
        assert await pool_used_numbers(db=db, pool=pool, branch=default_branch_scope_class) == [100, 101]

    async def test_widening_and_adding_ranges_keeps_the_numbers_already_handed_out(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        """The pool holds 10-12 (weight 10) and 16-18, and hands out 10-12 then 16."""
        pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(db=db, name="drained-pool", node="TestingTicket", node_attribute="ticket_id")
        await pool.save(db=db)
        await _create_range(db=db, branch=default_branch_scope_class, pool=pool, start=10, end=12, weight=10)
        upper_range_id = await _create_range(db=db, branch=default_branch_scope_class, pool=pool, start=16, end=18)
        for index in range(4):
            await _allocate_ticket(db=db, pool=pool, title=f"drained-{index}")
        assert await pool_used_numbers(db=db, pool=pool, branch=default_branch_scope_class) == [10, 11, 12, 16]

        widened = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": upper_range_id, "start": 14, "end": 18},
        )
        assert not widened.errors
        assert await _range_bounds(db=db, pool=pool) == [(10, 12), (14, 18)]
        assert await _utilization(db=db, branch=default_branch_scope_class, pool=pool) == {
            "count": 2,
            "utilization": _percent(4, 8),
            "edges": [
                {"node": {"display_label": "10 - 12", "utilization": 100.0}},
                {"node": {"display_label": "14 - 18", "utilization": _percent(1, 5)}},
            ],
        }
        await _allocate_ticket(db=db, pool=pool, title="drained-after-widening")
        assert await _ticket_ids(db=db, branch=default_branch_scope_class, titles=["drained-after-widening"]) == {
            "drained-after-widening": 14
        }

        await _create_range(db=db, branch=default_branch_scope_class, pool=pool, start=20, end=22)
        assert await _utilization(db=db, branch=default_branch_scope_class, pool=pool) == {
            "count": 3,
            "utilization": _percent(5, 11),
            "edges": [
                {"node": {"display_label": "10 - 12", "utilization": 100.0}},
                {"node": {"display_label": "14 - 18", "utilization": _percent(2, 5)}},
                {"node": {"display_label": "20 - 22", "utilization": 0.0}},
            ],
        }

    async def test_range_overlapping_others_of_its_pool_is_refused_naming_them(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, two_range_pool: TwoRangePool
    ) -> None:
        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": two_range_pool.pool.get_id(), "start": 150, "end": 350, "weight": None},
        )

        assert result.errors
        assert str(result.errors[0].message) == (
            f"Range 150 - 350 overlaps 100 - 200 ({two_range_pool.low.get_id()}), 300 - 400 ({two_range_pool.high.get_id()})"
        )
        assert await _range_bounds(db=db, pool=two_range_pool.pool) == [(100, 200), (300, 400)]

    async def test_range_moved_onto_another_range_of_its_pool_is_refused(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, two_range_pool: TwoRangePool
    ) -> None:
        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": two_range_pool.high.get_id(), "start": 100, "end": 200},
        )

        assert result.errors
        assert str(result.errors[0].message) == f"Range 100 - 200 overlaps 100 - 200 ({two_range_pool.low.get_id()})"
        assert await _range_bounds(db=db, pool=two_range_pool.pool) == [(100, 200), (300, 400)]

    async def test_range_resized_within_free_space_of_its_pool_is_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool, low = await _create_pool_with_range(db=db, name="resized-range-pool", start=100, end=200)
        await add_pool_range(db=db, pool=pool, start=300, end=400)

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": low.get_id(), "start": 150, "end": 299},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolRangeUpdate"]["ok"]
        assert await _range_bounds(db=db, pool=pool) == [(150, 299), (300, 400)]

    async def test_upsert_refuses_an_overlapping_range_whether_it_updates_or_creates(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, two_range_pool: TwoRangePool
    ) -> None:
        pool_id = two_range_pool.pool.get_id()

        updated = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_RANGE,
            variables={"range_id": two_range_pool.high.get_id(), "pool_id": pool_id, "start": 150, "end": 250},
        )
        created = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_NEW_RANGE,
            variables={"pool_id": pool_id, "start": 150, "end": 250},
        )

        expected = f"Range 150 - 250 overlaps 100 - 200 ({two_range_pool.low.get_id()})"
        assert updated.errors
        assert str(updated.errors[0].message) == expected
        assert created.errors
        assert str(created.errors[0].message) == expected
        assert await _range_bounds(db=db, pool=two_range_pool.pool) == [(100, 200), (300, 400)]

    async def test_backwards_range_is_refused_on_create_and_update(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, two_range_pool: TwoRangePool
    ) -> None:
        created = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": two_range_pool.pool.get_id(), "start": 400, "end": 300, "weight": None},
        )
        updated = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": two_range_pool.low.get_id(), "start": 200, "end": 100},
        )

        assert created.errors
        assert str(created.errors[0].message) == "Range end (300) cannot be lower than start (400)"
        assert updated.errors
        assert str(updated.errors[0].message) == "Range end (100) cannot be lower than start (200)"
        assert await _range_bounds(db=db, pool=two_range_pool.pool) == [(100, 200), (300, 400)]

    @pytest.mark.parametrize("case", ONE_BOUND_CASES, ids=lambda case: case.name)
    async def test_range_created_with_one_bound_leaves_the_other_open(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: OpenBoundCase
    ) -> None:
        pool = await _create_pool(db=db, name=f"one-bound-pool-{case.name}")

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": pool.get_id(), "start": case.start, "end": case.end, "weight": None},
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolRangeCreate"]["object"]
        assert (created["start"]["value"], created["end"]["value"]) == (case.start, case.end)
        assert await _shorthand_and_ranges(db=db, pool_id=pool.get_id()) == (
            (case.start, case.end),
            [(case.start, case.end)],
        )

    async def test_range_created_without_bounds_spans_every_number(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool = await _create_pool(db=db, name="unbounded-range-pool")

        result = await _execute(
            db=db, branch=default_branch_scope_class, source=CREATE_RANGE, variables={"pool_id": pool.get_id()}
        )

        assert not result.errors
        assert await _shorthand_and_ranges(db=db, pool_id=pool.get_id()) == ((None, None), [(None, None)])

    @pytest.mark.parametrize("case", REMOVED_BOUND_CASES, ids=lambda case: case.name)
    async def test_range_update_removing_a_bound_opens_it(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: OpenBoundCase
    ) -> None:
        pool, held_range = await _create_pool_with_range(
            db=db, name=f"removed-bound-pool-{case.name}", start=100, end=200
        )

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": held_range.get_id(), "start": case.start, "end": case.end},
        )

        assert not result.errors
        assert await _shorthand_and_ranges(db=db, pool_id=pool.get_id()) == (
            (case.start, case.end),
            [(case.start, case.end)],
        )

    @pytest.mark.parametrize("case", OPEN_OVERLAP_CASES, ids=lambda case: case.name)
    async def test_open_range_overlapping_another_range_of_its_pool_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        two_range_pool: TwoRangePool,
        case: OpenOverlapCase,
    ) -> None:
        overlapped = f"100 - 200 ({two_range_pool.low.get_id()})"
        if case.overlaps_the_high_range:
            overlapped += f", 300 - 400 ({two_range_pool.high.get_id()})"

        created = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": two_range_pool.pool.get_id(), "start": case.start, "end": case.end, "weight": None},
        )

        assert [error.message for error in created.errors or []] == [f"Range {case.label} overlaps {overlapped}"]
        assert await _range_bounds(db=db, pool=two_range_pool.pool) == [(100, 200), (300, 400)]

    async def test_two_pools_on_one_attribute_may_hold_overlapping_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        first_pool = await _create_pool(db=db, name="first-pool")
        second_pool = await _create_pool(db=db, name="second-pool")

        await _create_range(db=db, branch=default_branch_scope_class, pool=first_pool, start=100, end=200)
        await _create_range(db=db, branch=default_branch_scope_class, pool=second_pool, start=150, end=250)

        assert await _range_bounds(db=db, pool=first_pool) == [(100, 200)]
        assert await _range_bounds(db=db, pool=second_pool) == [(150, 250)]

    async def test_range_cannot_move_to_another_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool, held_range = await _create_pool_with_range(db=db, name="range-owner-pool", start=100, end=200)
        other_pool = await _create_pool(db=db, name="other-pool")

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=MOVE_RANGE,
            variables={"range_id": held_range.get_id(), "pool_id": other_pool.get_id()},
        )

        assert result.errors
        assert str(result.errors[0].message) == "The field 'pool' can't be changed."
        assert await _range_bounds(db=db, pool=pool) == [(100, 200)]
        assert await _range_bounds(db=db, pool=other_pool) == []

    async def test_removing_the_last_range_leaves_an_empty_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool, held_range = await _create_pool_with_range(db=db, name="emptied-pool", start=100, end=200)

        deleted = await _execute(
            db=db, branch=default_branch_scope_class, source=DELETE_RANGE, variables={"range_id": held_range.get_id()}
        )
        read = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=QUERY_POOL_WITH_RANGES,
            variables={"pool_id": pool.get_id()},
        )

        assert not deleted.errors
        assert deleted.data
        assert deleted.data["CoreNumberPoolRangeDelete"]["ok"]
        assert not read.errors
        assert read.data
        node = read.data["CoreNumberPool"]["edges"][0]["node"]
        assert node["ranges"]["count"] == 0
        assert node["start_range"]["value"] is None
        assert node["end_range"]["value"] is None

    async def test_shorthand_mirrors_the_range_set_after_every_write(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        async def run(source: str, variables: dict[str, Any]) -> dict[str, Any]:
            result = await _execute(db=db, branch=default_branch_scope_class, source=source, variables=variables)
            assert not result.errors
            assert result.data
            return result.data

        created = await run(CREATE_POOL_WITHOUT_BOUNDS, {})
        pool_id = created["CoreNumberPoolCreate"]["object"]["id"]
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((None, None), [(None, None)])

        await run(UPDATE_POOL_SHORTHAND, {"pool_id": pool_id, "start": 10, "end": 20})
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((10, 20), [(10, 20)])

        created_range = await run(CREATE_RANGE, {"pool_id": pool_id, "start": 30, "end": 40, "weight": None})
        second_range_id = created_range["CoreNumberPoolRangeCreate"]["object"]["id"]
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((None, None), [(10, 20), (30, 40)])

        first_range_id = (await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id))[0].get_id()
        await run(
            UPDATE_POOL_RANGES, {"pool_id": pool_id, "ranges": [{"start": 10, "end": 20}, {"start": 30, "end": 40}]}
        )
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((None, None), [(10, 20), (30, 40)])

        await run(DELETE_RANGE, {"range_id": second_range_id})
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((10, 20), [(10, 20)])

        await run(UPDATE_RANGE, {"range_id": first_range_id, "start": 12, "end": 22})
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((12, 22), [(12, 22)])

        await run(UPDATE_POOL_RANGES, {"pool_id": pool_id, "ranges": [{"start": 12, "end": 22}]})
        assert await _shorthand_and_ranges(db=db, pool_id=pool_id) == ((12, 22), [(12, 22)])

    async def test_pool_update_with_ranges_recomputes_the_shorthand_from_the_stored_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        """The second range is saved outside the mutations so the stored shorthand starts out of step with the ranges."""
        pool, low = await _create_pool_with_range(db=db, name="recomputed-shorthand-pool", start=10, end=20)
        high = await add_pool_range(db=db, pool=pool, start=30, end=40)
        assert await _shorthand_and_ranges(db=db, pool_id=pool.get_id()) == ((10, 20), [(10, 20), (30, 40)])

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": pool.get_id(), "ranges": [{"start": 10, "end": 20}, {"start": 30, "end": 40}]},
        )

        assert not result.errors
        assert await _shorthand_and_ranges(db=db, pool_id=pool.get_id()) == ((None, None), [(10, 20), (30, 40)])
        assert [item.get_id() for item in await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())] == [
            low.get_id(),
            high.get_id(),
        ]

    async def test_pool_update_with_valid_ranges_repairs_a_pool_whose_stored_ranges_overlap(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        """The overlapping range is saved outside the mutations, which refuse to store it."""
        pool, low = await _create_pool_with_range(db=db, name="repaired-pool", start=10, end=20)
        high = await add_pool_range(db=db, pool=pool, start=15, end=25)

        result = await _execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": pool.get_id(), "ranges": [{"start": 10, "end": 20}, {"start": 30, "end": 40}]},
        )

        assert not result.errors
        assert await _shorthand_and_ranges(db=db, pool_id=pool.get_id()) == ((None, None), [(10, 20), (30, 40)])
        kept_id, new_id = [
            item.get_id() for item in await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        ]
        assert kept_id == low.get_id()
        assert new_id != high.get_id()
