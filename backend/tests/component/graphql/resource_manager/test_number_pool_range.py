from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
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


async def _create_pool(db: InfrahubDatabase) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db, name="range-pool", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=100
    )
    await pool.save(db=db)
    return pool


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
    assert node["start_range"]["value"] == 1
    assert node["end_range"]["value"] == 100


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
