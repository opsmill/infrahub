from __future__ import annotations

import weakref
from functools import lru_cache
from inspect import isawaitable
from typing import TYPE_CHECKING, Any

from cachetools import LRUCache
from graphql import GraphQLSchema, execute, parse, validate
from graphql.error import GraphQLError
from graphql.execution import ExecutionResult
from graphql.type import validate_schema

if TYPE_CHECKING:
    from collections.abc import Callable

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
    query_str = _query_text(query)
    if _has_expand_directive(query_str):
        return parse(query)
    return _cached_parse(query_str)


def _query_text(query: str | Source) -> str:
    return query if isinstance(query, str) else query.body


def _has_expand_directive(query: str) -> bool:
    return "@expand" in query


MAX_CACHED_VALID_DOCUMENTS_PER_SCHEMA = 1024

_valid_documents_by_schema: weakref.WeakKeyDictionary[GraphQLSchema, LRUCache[DocumentNode, bool]] = (
    weakref.WeakKeyDictionary()
)


def cached_validate(schema: GraphQLSchema, document_ast: DocumentNode) -> list[GraphQLError]:
    """Validate a document against a schema, remembering valid documents for as long as the schema object exists.

    Errors are not cached because the traceback of a raised error can reference the schema and keep it alive.
    """
    valid_documents = _valid_documents_by_schema.get(schema)
    if valid_documents is None:
        valid_documents = _valid_documents_by_schema[schema] = LRUCache(maxsize=MAX_CACHED_VALID_DOCUMENTS_PER_SCHEMA)
    if valid_documents.get(document_ast, False):
        return []
    errors = validate(schema, document_ast)
    if not errors:
        valid_documents[document_ast] = True
    return errors


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
    # graphql-core stores the result on the schema object, so only the first call per schema does the work.
    schema_validation_errors = validate_schema(schema)
    if schema_validation_errors:
        return ExecutionResult(data=None, errors=schema_validation_errors)

    # Parse
    try:
        document = cached_parse(source)
    except GraphQLError as error:
        return ExecutionResult(data=None, errors=[error])

    if _has_expand_directive(_query_text(source)):
        # The document of an @expand query is parsed again and changed on every run, so it would never match a cached one.
        validation_errors = validate(schema, document)
    else:
        validation_errors = cached_validate(schema, document)
    if validation_errors:
        return ExecutionResult(data=None, errors=validation_errors)

    # Execute
    result = execute(
        schema=schema,
        document=document,
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

    if isawaitable(result):
        return await result

    return result
