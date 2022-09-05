from graphql import graphql
import graphene

from infrahub.core import get_branch
from infrahub.core.timestamp import Timestamp
from infrahub.core.manager import NodeManager
from .generator import generate_mutation_mixin, generate_query_mixin
from .schema import InfrahubBaseMutation, InfrahubBaseQuery
from .subscription import InfrahubBaseSubscription


def get_gql_query(branch=None):

    QueryMixin = generate_query_mixin(branch=branch)

    class Query(InfrahubBaseQuery, QueryMixin):
        pass

    return Query


def get_gql_mutation(branch=None):

    MutationMixin = generate_mutation_mixin(branch=branch)

    class Mutation(InfrahubBaseMutation, MutationMixin):
        pass

    return Mutation


def get_gql_subscription(branch=None):
    class Subscription(InfrahubBaseSubscription):
        pass

    return Subscription


async def execute_query(name, params=None, branch=None, at=None):

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
