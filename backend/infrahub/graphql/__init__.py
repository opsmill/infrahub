from __future__ import annotations

from typing import TYPE_CHECKING, Union

import graphene
from graphql import GraphQLSchema, graphql

from infrahub.core import get_branch, registry
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp

from .generator import (
    generate_mutation_mixin,
    generate_object_types,
    generate_query_mixin,
)
from .schema import InfrahubBaseMutation, InfrahubBaseQuery
from .subscription import InfrahubBaseSubscription

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


async def generate_graphql_schema(
    session: AsyncSession,
    include_query: bool = True,
    include_mutation: bool = True,
    include_subscription: bool = True,
    include_types: bool = True,
    branch: Union[Branch, str] = None,
) -> GraphQLSchema:
    if include_types:
        await generate_object_types(session=session, branch=branch)
        types_dict = registry.get_all_graphql_type(branch=branch)
        types = list(types_dict.values())
    else:
        types = []

    query = await get_gql_query(session=session, branch=branch) if include_query else None
    mutation = await get_gql_mutation(session=session, branch=branch) if include_mutation else None
    subscription = await get_gql_subscription(session=session, branch=branch) if include_subscription else None

    graphene_schema = graphene.Schema(
        query=query, mutation=mutation, subscription=subscription, types=types, auto_camelcase=False
    )
    return graphene_schema.graphql_schema


async def get_gql_query(session: AsyncSession, branch: Union[Branch, str] = None):
    QueryMixin = await generate_query_mixin(session=session, branch=branch)

    class Query(InfrahubBaseQuery, QueryMixin):
        pass

    return Query


async def get_gql_mutation(session: AsyncSession, branch: Union[Branch, str] = None):
    MutationMixin = await generate_mutation_mixin(session=session, branch=branch)

    class Mutation(InfrahubBaseMutation, MutationMixin):
        pass

    return Mutation


async def get_gql_subscription(
    session: AsyncSession, branch: Union[Branch, str] = None
):  # pylint: disable=unused-argument
    class Subscription(InfrahubBaseSubscription):
        pass

    return Subscription


async def execute_query(
    name: str,
    session: AsyncSession,
    params: Optional[dict] = None,
    branch: Union[Branch, str] = None,
    at: Union[Timestamp, str] = None,
) -> ExecutionResult:
    """Helper function to Execute a GraphQL Query."""

    branch = branch or await get_branch(session=session, branch=branch)
    at = Timestamp(at)

    items = await NodeManager.query(session=session, schema="GraphQLQuery", filters={name: name}, branch=branch, at=at)
    if not items:
        raise ValueError(f"Unable to find the GraphQLQuery {name}")

    graphql_query = items[0]

    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session, branch=branch), auto_camelcase=False).graphql_schema,
        source=graphql_query.query.value,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
        },
        root_value=None,
        variable_values=params or {},
    )

    return result
