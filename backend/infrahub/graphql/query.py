from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

import graphene
from graphql import graphql

from infrahub.core import get_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp

from .generator import generate_query_mixin
from .schema import InfrahubBaseQuery

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


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


async def get_gql_query(session: AsyncSession, branch: Union[Branch, str] = None) -> type[InfrahubBaseQuery]:
    QueryMixin = await generate_query_mixin(session=session, branch=branch)

    class Query(InfrahubBaseQuery, QueryMixin):
        pass

    return Query
