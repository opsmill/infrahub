import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator

from graphene import Schema
from graphql import GraphQLResolveInfo, graphql

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGraphQLQuery
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.resolvers.many_relationship import ManyRelationshipResolver
from infrahub.graphql.resolvers.single_relationship import SingleRelationshipResolver
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger(name="infrahub.graphql")


async def resolver_graphql_query(
    parent: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    name: str,
    graphql_schema: Schema,
    params: dict[str, Any] | None = None,
    interval: int = 10,
) -> AsyncGenerator[dict[str, Any], None]:
    graphql_context: GraphqlContext = info.context
    at = Timestamp()

    async with graphql_context.db.start_session(read_only=True) as db:
        # Find the GraphQLQuery and the GraphQL Schema
        graphql_query = await NodeManager.get_one_by_default_filter(
            db=db, id=name, kind=CoreGraphQLQuery, branch=graphql_context.branch, at=at
        )
        if not graphql_query:
            raise ValueError(f"Unable to find the {InfrahubKind.GRAPHQLQUERY} {name}")

    while True:
        async with graphql_context.db.start_session(read_only=True) as db:
            result = await graphql(
                schema=graphql_schema,
                source=graphql_query.query.value,
                context_value=graphql_context.__class__(
                    db=db,
                    branch=graphql_context.branch,
                    at=Timestamp(),
                    related_node_ids=set(),
                    types=graphql_context.types,
                    single_relationship_resolver=SingleRelationshipResolver(),
                    many_relationship_resolver=ManyRelationshipResolver(),
                ),
                root_value=None,
                variable_values=params or {},
            )
            if result.data:
                yield result.data

        await asyncio.sleep(delay=float(interval))
