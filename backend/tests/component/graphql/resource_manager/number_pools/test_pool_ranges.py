from typing import Any

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
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

CREATE_RANGE = """
mutation CreateRange($pool_id: String!, $start: BigInt!, $end: BigInt!, $weight: BigInt) {
    CoreNumberPoolRangeCreate(data: {
        start: { value: $start }
        end: { value: $end }
        allocation_weight: { value: $weight }
        pool: { id: $pool_id }
    }) {
        ok
        object {
            id
            start { value }
            end { value }
            allocation_weight { value }
        }
    }
}
"""

DELETE_POOL = """
mutation DeletePool($pool_id: String!) {
    CoreNumberPoolDelete(data: { id: $pool_id }) {
        ok
    }
}
"""

UPDATE_RANGE = """
mutation UpdateRange($range_id: String!, $start: BigInt!, $end: BigInt!) {
    CoreNumberPoolRangeUpdate(data: { id: $range_id, start: { value: $start }, end: { value: $end } }) {
        ok
    }
}
"""

UPSERT_RANGE = """
mutation UpsertRange($range_id: String!, $pool_id: String!, $start: BigInt!, $end: BigInt!) {
    CoreNumberPoolRangeUpsert(data: {
        id: $range_id
        start: { value: $start }
        end: { value: $end }
        pool: { id: $pool_id }
    }) {
        ok
    }
}
"""

UPSERT_NEW_RANGE = """
mutation UpsertNewRange($pool_id: String!, $start: BigInt!, $end: BigInt!) {
    CoreNumberPoolRangeUpsert(data: { start: { value: $start }, end: { value: $end }, pool: { id: $pool_id } }) {
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

DELETE_RANGE = """
mutation DeleteRange($range_id: String!) {
    CoreNumberPoolRangeDelete(data: { id: $range_id }) {
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


async def _create_pool(db: InfrahubDatabase, name: str = "range-pool") -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=100)
    await pool.save(db=db)
    return pool


async def _create_pool_with_range(db: InfrahubDatabase, start: int, end: int) -> tuple[CoreNumberPool, Node]:
    """Build a pool whose shorthand matches its single range, so it allocates from that range."""
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db, name="live-pool", node="TestingTicket", node_attribute="ticket_id", start_range=start, end_range=end
    )
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


async def _ticket_ids(db: InfrahubDatabase, branch: Branch) -> dict[str, int]:
    tickets = await NodeManager.query(db=db, schema=TICKET.kind, branch=branch)
    return {ticket.get_attribute("title").value: ticket.get_attribute("ticket_id").value for ticket in tickets}


async def _range_bounds(db: InfrahubDatabase, pool: CoreNumberPool) -> list[tuple[int, int]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
    return [(int(pool_range.start.value), int(pool_range.end.value)) for pool_range in ranges]


async def _create_range(
    db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool, start: int, end: int, weight: int | None = None
) -> str:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_RANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.get_id(), "start": start, "end": end, "weight": weight},
    )
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPoolRangeCreate"]["object"]["id"]


async def test_range_created_through_mutation_is_listed_under_its_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool = await _create_pool(db=db)

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_RANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.get_id(), "start": 10, "end": 20, "weight": 5},
    )

    assert not result.errors
    assert result.data
    created = result.data["CoreNumberPoolRangeCreate"]
    assert created["ok"]
    assert created["object"]["start"]["value"] == 10
    assert created["object"]["end"]["value"] == 20
    assert created["object"]["allocation_weight"]["value"] == 5

    range_node = await NodeManager.get_one(id=created["object"]["id"], db=db, branch=default_branch)
    assert range_node is not None
    assert range_node.get_kind() == InfrahubKind.NUMBERPOOLRANGE
    assert (range_node.start.value, range_node.end.value) == (10, 20)
    assert range_node.allocation_weight.value == 5
    assert (await range_node.pool.get_peer(db=db)).get_id() == pool.get_id()

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    read = await graphql(
        schema=gql_params.schema,
        source=QUERY_POOL_WITH_RANGES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.get_id()},
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
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool = await _create_pool(db=db)

    for start, end in ((30, 40), (10, 20)):
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_RANGE,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"pool_id": pool.get_id(), "start": start, "end": end, "weight": None},
        )
        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolRangeCreate"]["ok"]
        assert result.data["CoreNumberPoolRangeCreate"]["object"]["allocation_weight"]["value"] is None

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    read = await graphql(
        schema=gql_params.schema,
        source=QUERY_POOL_WITH_RANGES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.get_id()},
    )

    assert not read.errors
    assert read.data
    node = read.data["CoreNumberPool"]["edges"][0]["node"]
    assert node["ranges"]["count"] == 2
    bounds = [(edge["node"]["start"]["value"], edge["node"]["end"]["value"]) for edge in node["ranges"]["edges"]]
    assert bounds == [(10, 20), (30, 40)]


async def test_range_display_label_is_its_bounds(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool = await _create_pool(db=db)
    await _create_range(db=db, branch=default_branch, pool=pool, start=10, end=20)

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    read = await graphql(
        schema=gql_params.schema,
        source=QUERY_POOL_WITH_RANGES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.get_id()},
    )

    assert not read.errors
    assert read.data
    node = read.data["CoreNumberPool"]["edges"][0]["node"]
    assert [edge["node"]["display_label"] for edge in node["ranges"]["edges"]] == ["10 - 20"]


async def test_deleting_a_pool_deletes_its_ranges(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool = await _create_pool(db=db)
    range_ids = [
        await _create_range(db=db, branch=default_branch, pool=pool, start=10, end=20),
        await _create_range(db=db, branch=default_branch, pool=pool, start=30, end=40),
    ]

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    deleted = await graphql(
        schema=gql_params.schema,
        source=DELETE_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.get_id()},
    )

    assert not deleted.errors
    assert deleted.data
    assert deleted.data["CoreNumberPoolDelete"]["ok"]

    assert await NodeManager.get_one(id=pool.get_id(), db=db, branch=default_branch) is None
    remaining = await NodeManager.get_many(ids=range_ids, db=db, branch=default_branch)
    assert remaining == {}


async def test_adding_a_range_to_a_pool_in_use_leaves_allocated_values_untouched(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool, _ = await _create_pool_with_range(db=db, start=100, end=200)
    await _allocate_ticket(db=db, pool=pool, title="first")
    await _allocate_ticket(db=db, pool=pool, title="second")
    assert await _ticket_ids(db=db, branch=default_branch) == {"first": 100, "second": 101}

    result = await _execute(
        db=db,
        branch=default_branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool.get_id(), "start": 205, "end": 300, "weight": None},
    )

    assert not result.errors
    assert result.data
    assert result.data["CoreNumberPoolRangeCreate"]["ok"]
    assert await _range_bounds(db=db, pool=pool) == [(100, 200), (205, 300)]
    assert await _ticket_ids(db=db, branch=default_branch) == {"first": 100, "second": 101}
    assert sorted(await NumberPoolRepository(db=db).get_used(pool=pool, branch=default_branch)) == [100, 101]


async def test_removing_a_range_holding_an_allocated_value_keeps_the_value(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool, held_range = await _create_pool_with_range(db=db, start=205, end=300)
    await _allocate_ticket(db=db, pool=pool, title="held")
    await _create_range(db=db, branch=default_branch, pool=pool, start=100, end=200)
    assert await _range_bounds(db=db, pool=pool) == [(100, 200), (205, 300)]

    result = await _execute(
        db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": held_range.get_id()}
    )

    assert not result.errors
    assert result.data
    assert result.data["CoreNumberPoolRangeDelete"]["ok"]
    assert await NodeManager.get_one(id=held_range.get_id(), db=db, branch=default_branch) is None
    assert await _range_bounds(db=db, pool=pool) == [(100, 200)]
    assert await _ticket_ids(db=db, branch=default_branch) == {"held": 205}
    assert await NumberPoolRepository(db=db).get_used(pool=pool, branch=default_branch) == [205]


async def test_range_overlapping_others_of_its_pool_is_refused_naming_them(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, low = await _create_pool_with_range(db=db, start=100, end=200)
    high = await add_pool_range(db=db, pool=pool, start=300, end=400)

    result = await _execute(
        db=db,
        branch=default_branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool.get_id(), "start": 150, "end": 350, "weight": None},
    )

    assert result.errors
    assert str(result.errors[0].message) == (
        f"Range 150-350 overlaps 100-200 ({low.get_id()}), 300-400 ({high.get_id()})"
    )
    assert await _range_bounds(db=db, pool=pool) == [(100, 200), (300, 400)]


async def test_range_moved_onto_another_range_of_its_pool_is_refused(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, low = await _create_pool_with_range(db=db, start=100, end=200)
    high = await add_pool_range(db=db, pool=pool, start=300, end=400)

    result = await _execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": high.get_id(), "start": 100, "end": 200},
    )

    assert result.errors
    assert str(result.errors[0].message) == f"Range 100-200 overlaps 100-200 ({low.get_id()})"
    assert await _range_bounds(db=db, pool=pool) == [(100, 200), (300, 400)]


async def test_range_resized_within_free_space_of_its_pool_is_accepted(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, low = await _create_pool_with_range(db=db, start=100, end=200)
    await add_pool_range(db=db, pool=pool, start=300, end=400)

    result = await _execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": low.get_id(), "start": 150, "end": 299},
    )

    assert not result.errors
    assert result.data
    assert result.data["CoreNumberPoolRangeUpdate"]["ok"]
    assert await _range_bounds(db=db, pool=pool) == [(150, 299), (300, 400)]


async def test_upsert_refuses_an_overlapping_range_whether_it_updates_or_creates(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, low = await _create_pool_with_range(db=db, start=100, end=200)
    high = await add_pool_range(db=db, pool=pool, start=300, end=400)

    updated = await _execute(
        db=db,
        branch=default_branch,
        source=UPSERT_RANGE,
        variables={"range_id": high.get_id(), "pool_id": pool.get_id(), "start": 150, "end": 250},
    )
    created = await _execute(
        db=db,
        branch=default_branch,
        source=UPSERT_NEW_RANGE,
        variables={"pool_id": pool.get_id(), "start": 150, "end": 250},
    )

    assert updated.errors
    assert str(updated.errors[0].message) == f"Range 150-250 overlaps 100-200 ({low.get_id()})"
    assert created.errors
    assert str(created.errors[0].message) == f"Range 150-250 overlaps 100-200 ({low.get_id()})"
    assert await _range_bounds(db=db, pool=pool) == [(100, 200), (300, 400)]


async def test_backwards_range_is_refused_on_create_and_update(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, held_range = await _create_pool_with_range(db=db, start=100, end=200)

    created = await _execute(
        db=db,
        branch=default_branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool.get_id(), "start": 400, "end": 300, "weight": None},
    )
    updated = await _execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": held_range.get_id(), "start": 200, "end": 100},
    )

    assert created.errors
    assert str(created.errors[0].message) == "Range end (300) cannot be lower than start (400)"
    assert updated.errors
    assert str(updated.errors[0].message) == "Range end (100) cannot be lower than start (200)"
    assert await _range_bounds(db=db, pool=pool) == [(100, 200)]


async def test_two_pools_on_one_attribute_may_hold_overlapping_ranges(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    first_pool = await _create_pool(db=db, name="first-pool")
    second_pool = await _create_pool(db=db, name="second-pool")

    await _create_range(db=db, branch=default_branch, pool=first_pool, start=100, end=200)
    await _create_range(db=db, branch=default_branch, pool=second_pool, start=150, end=250)

    assert await _range_bounds(db=db, pool=first_pool) == [(100, 200)]
    assert await _range_bounds(db=db, pool=second_pool) == [(150, 250)]


async def test_range_cannot_move_to_another_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, held_range = await _create_pool_with_range(db=db, start=100, end=200)
    other_pool = await _create_pool(db=db, name="other-pool")

    result = await _execute(
        db=db,
        branch=default_branch,
        source=MOVE_RANGE,
        variables={"range_id": held_range.get_id(), "pool_id": other_pool.get_id()},
    )

    assert result.errors
    assert str(result.errors[0].message) == "The field 'pool' can't be changed."
    assert await _range_bounds(db=db, pool=pool) == [(100, 200)]
    assert await _range_bounds(db=db, pool=other_pool) == []


async def test_removing_the_last_range_leaves_an_empty_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool, held_range = await _create_pool_with_range(db=db, start=100, end=200)

    deleted = await _execute(
        db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": held_range.get_id()}
    )
    read = await _execute(
        db=db, branch=default_branch, source=QUERY_POOL_WITH_RANGES, variables={"pool_id": pool.get_id()}
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
