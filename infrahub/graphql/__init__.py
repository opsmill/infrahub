from __future__ import annotations

from typing import TYPE_CHECKING, Union

from graphql import graphql
from graphql.execution import ExecutionResult
import graphene

from infrahub.core import get_branch
from infrahub.core.timestamp import Timestamp
from infrahub.core.manager import NodeManager
from .generator import generate_mutation_mixin, generate_query_mixin
from .schema import InfrahubBaseMutation, InfrahubBaseQuery
from .subscription import InfrahubBaseSubscription

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


def get_gql_query(branch: Union[Branch, str] = None):

    QueryMixin = generate_query_mixin(branch=branch)

    class Query(InfrahubBaseQuery, QueryMixin):
        pass

    return Query


def get_gql_mutation(branch: Union[Branch, str] = None):

    MutationMixin = generate_mutation_mixin(branch=branch)

    class Mutation(InfrahubBaseMutation, MutationMixin):
        pass

    return Mutation


def get_gql_subscription(branch: Union[Branch, str] = None):
    class Subscription(InfrahubBaseSubscription):
        pass

    return Subscription


async def execute_query(
    name, params: dict = None, branch: Union[Branch, str] = None, at: Union[Timestamp, str] = None
) -> ExecutionResult:
    """Helper function to Execute a GraphQL Query."""

    branch = branch or get_branch(branch)
    at = Timestamp(at)

    items = NodeManager.query("GraphQLQuery", filters={name: name}, branch=branch, at=at)
    if not items:
        raise ValueError(f"Unable to find the GraphQLQuery {name}")

    graphql_query = items[0]

    result = await graphql(
        graphene.Schema(query=get_gql_query(branch=branch), auto_camelcase=False).graphql_schema,
        source=graphql_query.query.value,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
        },
        root_value=None,
        variable_values=params or {},
    )

    return result
