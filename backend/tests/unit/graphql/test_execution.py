from typing import Any

from graphql import ExecutionContext, GraphQLError, GraphQLResolveInfo, build_schema

from infrahub.graphql.execution import execute_graphql_query

SCHEMA = build_schema(
    """
    type Query { greeting(name: String): String }
    type Mutation { rename(value: Int!): String }
    """
)


def reject_mutations(next: Any, root: Any, info: GraphQLResolveInfo, **kwargs: Any) -> Any:  # noqa: A002
    if info.operation.operation.value == "mutation":
        raise GraphQLError("mutations are rejected")
    return next(root, info, **kwargs)


async def test_middleware_runs_for_mutation() -> None:
    resolved: list[int] = []

    def rename(value: int, info: GraphQLResolveInfo) -> str:
        resolved.append(value)
        return "renamed"

    result = await execute_graphql_query(
        schema=SCHEMA,
        source="mutation { rename(value: 1) }",
        root_value={"rename": rename},
        middleware=[reject_mutations],
    )

    assert result.data == {"rename": None}
    assert [error.message for error in result.errors or []] == ["mutations are rejected"]
    assert resolved == []


async def test_invalid_variable_returns_graphql_error() -> None:
    result = await execute_graphql_query(
        schema=SCHEMA,
        source="mutation Rename($value: Int!) { rename(value: $value) }",
        variable_values={"value": "not-a-number"},
        middleware=[reject_mutations],
    )

    assert result.data is None
    assert [error.message for error in result.errors or []] == [
        "Variable '$value' got invalid value 'not-a-number'; Int cannot represent non-integer value: 'not-a-number'"
    ]


async def test_execution_context_class_is_used() -> None:
    created: list[ExecutionContext] = []

    class RecordingExecutionContext(ExecutionContext):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            created.append(self)

    result = await execute_graphql_query(
        schema=SCHEMA,
        source='{ greeting(name: "world") }',
        root_value={"greeting": "hello"},
        execution_context_class=RecordingExecutionContext,
    )

    assert result.errors is None
    assert result.data == {"greeting": "hello"}
    assert len(created) == 1
