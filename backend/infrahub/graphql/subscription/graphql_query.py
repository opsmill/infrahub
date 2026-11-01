from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGraphQLQuery
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse, execute_graphql_query
from infrahub.graphql.middleware import raise_on_mutation_for_branch_status
from infrahub.log import get_logger

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo, GraphQLSchema

    from infrahub.graphql.initialization import GraphqlContext

log = get_logger(name="infrahub.graphql")


async def resolver_graphql_query(
    parent: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    name: str,
    graphql_schema: GraphQLSchema,
    params: dict[str, Any] | None = None,
    interval: int = 10,
) -> AsyncGenerator[dict[str, Any], None]:
    # Deferred to break the schema initialization import cycle.
    from infrahub.graphql.api.dependencies import build_graphql_query_permission_checker  # noqa: PLC0415
    from infrahub.graphql.initialization import prepare_graphql_params  # noqa: PLC0415

    graphql_context: GraphqlContext = info.context
    account_session = graphql_context.active_account_session
    permission_checker = build_graphql_query_permission_checker()
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
            graphql_params = await prepare_graphql_params(
                db=db,
                branch=graphql_context.branch,
                account_session=account_session,
                request=graphql_context.request,
                service=graphql_context.service,
            )
            analyzed_query = InfrahubGraphQLQueryAnalyzer(
                query=graphql_query.query.value,
                schema=graphql_schema,
                schema_branch=db.schema.get_schema_branch(name=graphql_context.branch.name),
                query_variables=params,
                branch=graphql_context.branch,
                document=cached_parse(graphql_query.query.value),
            )
            await permission_checker.check(
                db=db,
                account_session=account_session,
                analyzed_query=analyzed_query,
                query_parameters=graphql_params,
                branch=graphql_context.branch,
            )
            result = await execute_graphql_query(
                schema=graphql_schema,
                source=graphql_query.query.value,
                context_value=graphql_params.context,
                root_value=None,
                variable_values=params or {},
                middleware=[raise_on_mutation_for_branch_status],
            )
            if result.data:
                yield result.data

        await asyncio.sleep(delay=float(interval))
