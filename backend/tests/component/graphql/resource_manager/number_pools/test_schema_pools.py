import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
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

from .helpers import DELETE_NUMBER_POOL, QUERY_NUMBER_POOL, UPDATE_NUMBER_POOL


@pytest.fixture
async def snow_ticket_schema_with_pools(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SNOW_TICKET_SCHEMA)
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    snps = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
    await snps.run()
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    graphql_registry.clear_cache()


async def test_delete_number_pool_in_use_by_numberpool_attribute(
    db: InfrahubDatabase, default_branch: Branch, snow_ticket_schema_with_pools: None
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    node_schema = registry.schema.get(name="SnowTask", branch=default_branch)
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
    db: InfrahubDatabase, default_branch: Branch, snow_ticket_schema_with_pools: None
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    node_schema = registry.schema.get(name="SnowTask", branch=default_branch)
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
