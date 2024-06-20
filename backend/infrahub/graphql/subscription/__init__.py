from typing import Any, Iterable, Optional

from graphene import ObjectType
from graphql import GraphQLResolveInfo

from .graphql_query import GraphQLQuerySubscription, resolver_graphql_query


class InfrahubBaseSubscription(ObjectType):
    query = GraphQLQuerySubscription

    @staticmethod
    async def subscribe_query(
        parent: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        name: str,
        params: Optional[dict[str, Any]] = None,
        interval: Optional[int] = 10,
    ) -> Iterable[dict]:
        async for result in resolver_graphql_query(
            parent=parent, info=info, name=name, params=params, interval=interval
        ):
            yield result
