from inspect import isawaitable

from graphql import build_schema, execute, get_introspection_query, parse

from infrahub.graphql.middleware import raise_on_mutation_for_branch_status

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
