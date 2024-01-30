from __future__ import annotations

from typing import TYPE_CHECKING, Union

import graphene

from infrahub.core import registry

from .generator import generate_mutation_mixin, generate_object_types
from .query import get_gql_query
from .schema import InfrahubBaseMutation
from .subscription import InfrahubBaseSubscription

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch.branch import Branch
    from infrahub.database import InfrahubDatabase


async def generate_graphql_schema(
    db: InfrahubDatabase,
    branch: Union[Branch, str],
    include_query: bool = True,
    include_mutation: bool = True,
    include_subscription: bool = True,
    include_types: bool = True,
) -> GraphQLSchema:
    if include_types:
        await generate_object_types(db=db, branch=branch)
        types_dict = registry.get_all_graphql_type(branch=branch)
        types = list(types_dict.values())
    else:
        types = []

    query = await get_gql_query(db=db, branch=branch) if include_query else None
    mutation = await get_gql_mutation(db=db, branch=branch) if include_mutation else None
    subscription = await get_gql_subscription(db=db, branch=branch) if include_subscription else None

    graphene_schema = graphene.Schema(
        query=query, mutation=mutation, subscription=subscription, types=types, auto_camelcase=False
    )

    return graphene_schema.graphql_schema


async def get_gql_mutation(db: InfrahubDatabase, branch: Union[Branch, str] = None) -> type[InfrahubBaseMutation]:
    MutationMixin = await generate_mutation_mixin(db=db, branch=branch)

    class Mutation(InfrahubBaseMutation, MutationMixin):
        pass

    return Mutation


async def get_gql_subscription(
    db: InfrahubDatabase,  # pylint: disable=unused-argument
    branch: Union[Branch, str] = None,  # pylint: disable=unused-argument
) -> type[InfrahubBaseSubscription]:
    class Subscription(InfrahubBaseSubscription):
        pass

    return Subscription
