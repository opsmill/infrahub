from inspect import isawaitable

import pytest
from graphql import build_schema, execute, get_introspection_query, parse

from infrahub.graphql.middleware import branch_status_middleware, raise_on_mutation_for_branch_status

SCHEMA = build_schema("type Query { greeting: String }")


def test_query_execution_stays_synchronous() -> None:
    """A query through the branch-status middleware must complete without touching the event loop.

    If the middleware returns a coroutine for non-mutation fields, every resolved field takes
    graphql-core's async completion path; a single IntrospectionQuery then blocks a worker's event
    loop for several seconds, starving every other request handled by that worker.
    """
    result = execute(
        SCHEMA,
        parse("{ greeting }"),
        root_value={"greeting": "hello"},
        middleware=[raise_on_mutation_for_branch_status],
    )

    assert not isawaitable(result)
    assert result.errors is None
    assert result.data == {"greeting": "hello"}


def test_introspection_execution_stays_synchronous() -> None:
    result = execute(
        SCHEMA,
        parse(get_introspection_query(descriptions=True)),
        middleware=[raise_on_mutation_for_branch_status],
    )

    assert not isawaitable(result)
    assert result.errors is None
    assert result.data is not None


@pytest.mark.parametrize(
    "query",
    [
        "{ greeting }",
        "query Greeting { greeting }",
        "fragment F on Query { greeting } query { ...F }",
    ],
)
def test_query_document_runs_without_the_branch_status_middleware(query: str) -> None:
    assert branch_status_middleware(parse(query)) is None


@pytest.mark.parametrize(
    "query",
    [
        "mutation { BranchCreate { ok } }",
        # A mutation whose top-level fields come from a fragment is still a mutation.
        "fragment F on Mutation { BranchCreate { ok } } mutation { ...F }",
        # The operation name is not known here, so a document with any mutation keeps the check.
        "query Greeting { greeting } mutation Create { BranchCreate { ok } }",
    ],
)
def test_mutation_document_runs_with_the_branch_status_middleware(query: str) -> None:
    assert branch_status_middleware(parse(query)) == [raise_on_mutation_for_branch_status]
