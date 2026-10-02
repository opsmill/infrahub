from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters, NumberPoolRangeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.schema import load_schema

from .helpers import (
    CREATE_RANGE,
    DELETE_RANGE,
    UPDATE_POOL_RANGES,
    UPDATE_POOL_SHORTHAND,
    UPDATE_RANGE,
    UPSERT_NEW_RANGE,
    UPSERT_RANGE,
    execute,
    range_details,
    shorthand,
)

CREATE_RANGE_BY_POOL_HFID = """
mutation CreateRangeByPoolHfid($pool_name: String!, $start: BigInt!, $end: BigInt!) {
    CoreNumberPoolRangeCreate(data: { start: { value: $start }, end: { value: $end }, pool: { hfid: [$pool_name] } }) {
        ok
    }
}
"""

UPDATE_POOL_RANGES_BY_HFID = """
mutation UpdatePoolRangesByHfid($pool_name: String!, $ranges: [RelatedNodeInput]) {
    CoreNumberPoolUpdate(data: { hfid: [$pool_name], ranges: $ranges }) {
        ok
    }
}
"""

UPSERT_POOL_RANGES_BY_ID = """
mutation UpsertPoolRangesById($pool_id: String!, $ranges: [RelatedNodeInput]) {
    CoreNumberPoolUpsert(data: { id: $pool_id, ranges: $ranges }) {
        ok
    }
}
"""

UPSERT_POOL_RANGES_BY_HFID = """
mutation UpsertPoolRangesByHfid($pool_name: String!, $ranges: [RelatedNodeInput]) {
    CoreNumberPoolUpsert(data: { hfid: [$pool_name], ranges: $ranges }) {
        ok
    }
}
"""

SCHEMA_POOL_RANGES_REFUSED = (
    "ranges can't be updated on schema defined pools, update the schema in the default branch instead"
)
SCHEMA_POOL_SHORTHAND_REFUSED = (
    "start_range or end_range can't be updated on schema defined pools, update the schema in the default branch instead"
)

COUNTER_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Counter",
            namespace="Testing",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(
                    name="counter",
                    kind="NumberPool",
                    optional=False,
                    read_only=True,
                    unique=True,
                    parameters=NumberPoolParameters(
                        ranges=[
                            NumberPoolRangeParameters(start=1, end=50),
                            NumberPoolRangeParameters(start=200, end=300),
                        ]
                    ),
                ),
            ],
        )
    ]
)


@dataclass
class SchemaPool:
    pool_id: str
    name: str
    range_ids: list[str]


@dataclass
class SchemaPoolWriteTestCase:
    name: str
    source: str
    variables: Callable[[SchemaPool], dict[str, Any]]
    expected_error: str


SCHEMA_POOL_WRITE_TEST_CASES: list[SchemaPoolWriteTestCase] = [
    SchemaPoolWriteTestCase(
        name="range_create_by_pool_id",
        source=CREATE_RANGE,
        variables=lambda pool: {"pool_id": pool.pool_id, "start": 400, "end": 500, "weight": None},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="range_create_by_pool_hfid",
        source=CREATE_RANGE_BY_POOL_HFID,
        variables=lambda pool: {"pool_name": pool.name, "start": 400, "end": 500},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="range_upsert_without_id_creates",
        source=UPSERT_NEW_RANGE,
        variables=lambda pool: {"pool_id": pool.pool_id, "start": 400, "end": 500},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="range_update",
        source=UPDATE_RANGE,
        variables=lambda pool: {"range_id": pool.range_ids[0], "start": 1, "end": 60},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="range_upsert_by_id_updates",
        source=UPSERT_RANGE,
        variables=lambda pool: {"range_id": pool.range_ids[0], "pool_id": pool.pool_id, "start": 1, "end": 60},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="range_delete",
        source=DELETE_RANGE,
        variables=lambda pool: {"range_id": pool.range_ids[0]},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="pool_update_ranges_by_id",
        source=UPDATE_POOL_RANGES,
        variables=lambda pool: {"pool_id": pool.pool_id, "ranges": [{"id": pool.range_ids[1]}]},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="pool_update_ranges_by_hfid",
        source=UPDATE_POOL_RANGES_BY_HFID,
        variables=lambda pool: {"pool_name": pool.name, "ranges": [{"id": pool.range_ids[1]}]},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="pool_upsert_ranges_by_id",
        source=UPSERT_POOL_RANGES_BY_ID,
        variables=lambda pool: {"pool_id": pool.pool_id, "ranges": [{"id": pool.range_ids[1]}]},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="pool_upsert_ranges_by_hfid",
        source=UPSERT_POOL_RANGES_BY_HFID,
        variables=lambda pool: {"pool_name": pool.name, "ranges": [{"id": pool.range_ids[1]}]},
        expected_error=SCHEMA_POOL_RANGES_REFUSED,
    ),
    SchemaPoolWriteTestCase(
        name="pool_shorthand_on_multi_range_pool",
        source=UPDATE_POOL_SHORTHAND,
        variables=lambda pool: {"pool_id": pool.pool_id, "start": 1, "end": 50},
        expected_error=SCHEMA_POOL_SHORTHAND_REFUSED,
    ),
]


class TestSchemaNumberPoolRangeWrites:
    """Range writes on a pool the schema declared with several ranges.

    The schema and its pool are loaded once for the class; every refusal leaves the pool as it found it.
    """

    @pytest.fixture(scope="class")
    async def counter_pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SchemaPool:
        await load_schema(db=db, schema=COUNTER_SCHEMA)
        upserter = SchemaNumberPoolUpserter(
            db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
        )
        await SchemaNumberPoolSynchronizer(
            db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
        ).run()
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        graphql_registry.clear_cache()
        default_branch_scope_class.update_schema_hash()

        pools = await NodeManager.query(
            db=db,
            schema=InfrahubKind.NUMBERPOOL,
            filters={"node__value": "TestingCounter", "node_attribute__value": "counter"},
            branch=default_branch_scope_class,
        )
        assert len(pools) == 1
        pool = pools[0]
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        return SchemaPool(pool_id=pool.get_id(), name=pool.name.value, range_ids=[item.get_id() for item in ranges])

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SCHEMA_POOL_WRITE_TEST_CASES])
    async def test_range_writes_on_a_schema_pool_are_refused_and_leave_it_untouched(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        counter_pool: SchemaPool,
        test_case: SchemaPoolWriteTestCase,
    ) -> None:
        ranges_before = [(counter_pool.range_ids[0], 1, 50, None), (counter_pool.range_ids[1], 200, 300, None)]
        assert await shorthand(db=db, pool_id=counter_pool.pool_id) == (None, None)
        assert await range_details(db=db, pool_id=counter_pool.pool_id) == ranges_before

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=test_case.source,
            variables=test_case.variables(counter_pool),
        )

        assert [error.message for error in result.errors or []] == [test_case.expected_error]
        assert await shorthand(db=db, pool_id=counter_pool.pool_id) == (None, None)
        assert await range_details(db=db, pool_id=counter_pool.pool_id) == ranges_before
