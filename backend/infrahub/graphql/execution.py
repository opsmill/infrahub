from __future__ import annotations

from functools import lru_cache
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Callable

from graphql import GraphQLSchema, execute, parse, validate
from graphql.error import GraphQLError
from graphql.execution import ExecutionResult
from graphql.type import validate_schema

if TYPE_CHECKING:
    from graphql import ExecutionContext, GraphQLFieldResolver, GraphQLTypeResolver
    from graphql.execution import Middleware
    from graphql.language import Source
    from graphql.language.ast import DocumentNode


@lru_cache(maxsize=1024)
def _cached_parse(query: str) -> DocumentNode:
    """Internal cached parse function for queries without @expand directive."""
    return parse(query)


def cached_parse(query: str | Source) -> DocumentNode:
    """Parse a GraphQL query string into a DocumentNode.

    Queries containing the @expand directive are not cached because the parser
    mutates the AST to add expanded fields, which would corrupt the cache.
    """
    query_str = query if isinstance(query, str) else query.body
    if "@expand" in query_str:
        return parse(query)
    return _cached_parse(query_str)


@lru_cache(maxsize=1024)
def cached_validate(schema: GraphQLSchema, document_ast: DocumentNode) -> list[GraphQLError]:
    return validate(schema, document_ast)


@lru_cache(maxsize=1024)
def cached_validate_schema(schema: GraphQLSchema) -> list[GraphQLError]:
    return validate_schema(schema)


async def execute_graphql_query(
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
    """Execute a query, return asynchronously only if necessary."""
    # Validate Schema
    schema_validation_errors = cached_validate_schema(schema)
    if schema_validation_errors:
        return ExecutionResult(data=None, errors=schema_validation_errors)

    # Parse
    try:
        document = cached_parse(source)
    except GraphQLError as error:
        return ExecutionResult(data=None, errors=[error])

    validation_errors = cached_validate(schema, document)
    if validation_errors:
        return ExecutionResult(data=None, errors=validation_errors)

    # Execute
    result = execute(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        None,
        middleware,
        execution_context_class,
        is_awaitable,
    )

    if isawaitable(result):
        return await result

    return result
