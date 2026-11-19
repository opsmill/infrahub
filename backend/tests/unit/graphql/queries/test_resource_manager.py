from __future__ import annotations

import pytest
from graphene import Schema
from graphql import GraphQLSchema, graphql, parse, validate
from infrahub_sdk import InfrahubClient
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.schema import NodeSchemaAPI

from infrahub.graphql.schema import InfrahubBaseQuery


@pytest.fixture
def pool_query_schema() -> GraphQLSchema:
    return Schema(query=InfrahubBaseQuery, auto_camelcase=False).graphql_schema


def test_sdk_pool_allocation_query_is_valid(pool_query_schema: GraphQLSchema) -> None:
    pool = InfrahubNode(
        client=InfrahubClient(),
        schema=NodeSchemaAPI(name="IPAddressPool", namespace="Core"),
        branch="main",
    )
    query = pool._pool_allocated_query(
        edge_fields=("id", "display_label", "kind", "branch", "identifier", "provenance")
    )

    assert validate(pool_query_schema, parse(query)) == []


@pytest.mark.parametrize(
    ("offset", "limit", "message"),
    [
        (-1, 10, "offset must be a non-negative integer"),
        (0, -1, "limit must be a non-negative integer"),
    ],
)
async def test_pool_pagination_rejects_negative_values_before_database_access(
    pool_query_schema: GraphQLSchema, offset: int, limit: int, message: str
) -> None:
    result = await graphql(
        pool_query_schema,
        """
        query($offset: Int!, $limit: Int!) {
            InfrahubResourcePoolAllocated(pool_id: "pool", resource_id: "resource", offset: $offset, limit: $limit) {
                count
            }
        }
        """,
        variable_values={"offset": offset, "limit": limit},
    )

    assert result.data is None
    assert result.errors is not None
    assert [error.message for error in result.errors] == [message]
