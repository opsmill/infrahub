import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.graphql import graphql
from tests.helpers.schema import SNOW_TICKET_SCHEMA, load_schema

from .helpers import DELETE_NUMBER_POOL, QUERY_NUMBER_POOL, UPDATE_NUMBER_POOL, range_details

UPSERT_NUMBER_POOL_BOUNDS_BY_ID = """
mutation UpsertNumberPoolBounds($id: String!, $start_range: BigInt!, $end_range: BigInt!) {
    CoreNumberPoolUpsert(data: { id: $id, start_range: { value: $start_range }, end_range: { value: $end_range } }) {
        ok
    }
}
"""


class TestSchemaNumberPools:
    """Mutations on a pool the schema created.

    The schema and its pools are loaded once for the class; every test leaves the pool as it found it.
    """

    @pytest.fixture(scope="class")
    async def snow_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SNOW_TICKET_SCHEMA)
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        snps = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
        await snps.run()
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        graphql_registry.clear_cache()
        default_branch_scope_class.update_schema_hash()

    async def test_delete_number_pool_in_use_by_numberpool_attribute(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, snow_schema: None
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        node_schema = registry.schema.get(name="SnowTask", branch=default_branch_scope_class)
        number_pool_attribute = node_schema.get_attribute(name="number")
        assert isinstance(number_pool_attribute.parameters, NumberPoolParameters)
        query_before_creation = await graphql(
            schema=gql_params.schema,
            source=QUERY_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": number_pool_attribute.parameters.number_pool_id,
            },
        )

        assert not query_before_creation.errors
        assert query_before_creation.data
        assert query_before_creation.data["CoreNumberPool"]["count"] == 1

        delete_fail = await graphql(
            schema=gql_params.schema,
            source=DELETE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": number_pool_attribute.parameters.number_pool_id,
            },
        )

        assert delete_fail.errors
        assert "Unable to delete number pool SnowTask.number is in use (branches: main)" in str(delete_fail.errors)

    async def test_update_schema_number_pool_range(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, snow_schema: None
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        node_schema = registry.schema.get(name="SnowTask", branch=default_branch_scope_class)
        number_pool_attribute = node_schema.get_attribute(name="number")
        assert isinstance(number_pool_attribute.parameters, NumberPoolParameters)
        query_before_creation = await graphql(
            schema=gql_params.schema,
            source=QUERY_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": number_pool_attribute.parameters.number_pool_id,
            },
        )

        assert not query_before_creation.errors
        assert query_before_creation.data
        assert query_before_creation.data["CoreNumberPool"]["count"] == 1

        update_forbidden = await graphql(
            schema=gql_params.schema,
            source=UPDATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": number_pool_attribute.parameters.number_pool_id,
                "start_range": 1,
                "end_range": 10,
            },
        )

        assert update_forbidden.errors
        assert (
            "start_range or end_range can't be updated on schema defined pools, update the schema in the default branch instead"
            in str(update_forbidden.errors)
        )

    async def test_upsert_of_schema_number_pool_bounds_is_refused_and_leaves_the_pool_untouched(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, snow_schema: None
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        node_schema = registry.schema.get(name="SnowTask", branch=default_branch_scope_class)
        number_pool_attribute = node_schema.get_attribute(name="number")
        assert isinstance(number_pool_attribute.parameters, NumberPoolParameters)
        pool_id = number_pool_attribute.parameters.number_pool_id
        pool = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)
        bounds_before = (pool.start_range.value, pool.end_range.value)
        ranges_before = await range_details(db=db, pool_id=pool_id)
        assert bounds_before[0] is not None
        assert bounds_before[1] is not None

        result = await graphql(
            schema=gql_params.schema,
            source=UPSERT_NUMBER_POOL_BOUNDS_BY_ID,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": pool_id, "start_range": bounds_before[0] + 1, "end_range": bounds_before[1]},
        )

        assert [error.message for error in result.errors or []] == [
            "start_range or end_range can't be updated on schema defined pools, update the schema in the default branch instead"
        ]
        pool_after = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)
        assert (pool_after.start_range.value, pool_after.end_range.value) == bounds_before
        assert await range_details(db=db, pool_id=pool_id) == ranges_before
