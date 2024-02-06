import asyncio
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional

from graphene import Field, Int, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLResolveInfo, graphql

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext

log = get_logger(name="infrahub.graphql")


async def resolver_graphql_query(
    parent: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
    name: str,
    params: Optional[Dict[str, Any]] = None,
    interval: Optional[int] = 10,
) -> Iterable[Dict]:
    context: GraphqlContext = info.context
    at = Timestamp()

    async with context.db.start_session() as db:
        # Find the GraphQLQuery and the GraphQL Schema
        graphql_query = await NodeManager.get_one_by_default_filter(
            db=db, id=name, schema_name=InfrahubKind.GRAPHQLQUERY, branch=context.branch, at=at
        )
        if not graphql_query:
            raise ValueError(f"Unable to find the {InfrahubKind.GRAPHQLQUERY} {name}")

        schema_branch = registry.schema.get_schema_branch(name=context.branch.name)
        graphql_schema = schema_branch.get_graphql_schema()

    while True:
        async with context.db.start_session() as db:
            result = await graphql(
                schema=graphql_schema,
                source=graphql_query.query.value,
                context_value=context.__class__(
                    db=db, branch=context.branch, at=Timestamp(), related_node_ids=set(), types=context.types
                ),
                root_value=None,
                variable_values=params or {},
            )
            yield result.data

        await asyncio.sleep(delay=interval)


GraphQLQuerySubscription = Field(
    GenericScalar(),
    name=String(),
    params=GenericScalar(required=False),
    interval=Int(required=False),
)
