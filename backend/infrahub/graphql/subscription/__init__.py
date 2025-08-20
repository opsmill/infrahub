from typing import Any, AsyncGenerator

from graphene import Field, Int, ObjectType, Schema, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLResolveInfo

from .graphql_query import resolver_graphql_query

GraphQLQuerySubscription = Field(
    GenericScalar(),
    name=String(),
    params=GenericScalar(required=False),
    interval=Int(required=False),
)


class InfrahubBaseSubscription(ObjectType):
    query = GraphQLQuerySubscription
    graphql_schema: Schema | None = None

    @classmethod
    async def subscribe_query(
        cls,
        parent: dict,
        info: GraphQLResolveInfo,
        name: str,
        params: dict[str, Any] | None = None,
        interval: int | None = 10,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not cls.graphql_schema:
            raise RuntimeError("Subscription initialized without graphql schema")
        if not interval:
            interval = 10
        async for result in resolver_graphql_query(
            parent=parent, info=info, name=name, graphql_schema=cls.graphql_schema, params=params, interval=interval
        ):
            yield result
