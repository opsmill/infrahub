from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphql import (
    ExecutionContext,
    ExecutionResult,
    GraphQLFieldResolver,
    GraphQLSchema,
    GraphQLTypeResolver,
    Middleware,
    Source,
)
from graphql import graphql as graphql_core

from infrahub.core.branch import Branch
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.auth import AccountSession
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


async def graphql(
    schema: GraphQLSchema,
    source: str | Source,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    middleware: Middleware | None = None,
    execution_context_class: type[ExecutionContext] | None = None,
    is_awaitable: Callable[[Any], bool] | None = None,
) -> ExecutionResult:
    """
    Call `graphql` from graphql core package, and log potential errors to have full stack trace.
    """

    result = await graphql_core(
        schema=schema,
        source=source,
        root_value=root_value,
        context_value=context_value,
        variable_values=variable_values,
        operation_name=operation_name,
        field_resolver=field_resolver,
        type_resolver=type_resolver,
        middleware=middleware,
        execution_context_class=execution_context_class,
        is_awaitable=is_awaitable,
    )
    if result.errors is not None:
        log = get_logger()
        for error in result.errors:
            if error.original_error:
                log.error("Unhandled exception occurred in resolvers", exc_info=error.original_error)
    return result


async def graphql_mutation(
    query: str,
    db: InfrahubDatabase,
    service: InfrahubServices,
    branch: Branch | None = None,
    variables: dict[str, Any] | None = None,
    account_session: AccountSession | None = None,
) -> ExecutionResult:
    branch = branch or await Branch.get_by_name(name="main", db=db)
    branch.update_schema_hash()
    variables = variables or {}
    gql_params = await prepare_graphql_params(
        db=db,
        branch=branch,
        service=service,
        account_session=account_session,
    )
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def graphql_query(
    query: str,
    db: InfrahubDatabase,
    branch: Branch | None = None,
    service: InfrahubServices | None = None,
    variables: dict[str, Any] | None = None,
    account_session: AccountSession | None = None,
) -> ExecutionResult:
    branch = branch or await Branch.get_by_name(name="main", db=db)
    variables = variables or {}
    branch.update_schema_hash()

    gql_params = await prepare_graphql_params(
        db=db,
        branch=branch,
        service=service,
        account_session=account_session,
    )
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
