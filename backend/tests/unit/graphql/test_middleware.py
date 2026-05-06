from dataclasses import dataclass
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from graphql import graphql
from graphql.type.definition import GraphQLField, GraphQLObjectType, GraphQLScalarType
from graphql.type.scalars import GraphQLBoolean, GraphQLString
from graphql.type.schema import GraphQLSchema

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.graphql.middleware import raise_on_mutation_for_branch_status


@dataclass
class _FakeBranch:
    name: str = "feature-x"


@dataclass
class _FakeContext:
    db: object
    branch: _FakeBranch


def _build_schema_with_nested_mutation() -> GraphQLSchema:
    # graphql-core's GraphQLNamedType.__new__ is annotated to return the base class, so the
    # type checker widens every constructor result to GraphQLNamedType. We cast back to the
    # concrete subtype so GraphQLField / GraphQLSchema accept these values.
    string_type = cast("GraphQLScalarType", GraphQLString)
    bool_type = cast("GraphQLScalarType", GraphQLBoolean)
    nested_type = cast(
        "GraphQLObjectType",
        GraphQLObjectType(
            name="Nested",
            fields={"value": GraphQLField(string_type, resolve=lambda *_: "leaf")},
        ),
    )
    payload_type = cast(
        "GraphQLObjectType",
        GraphQLObjectType(
            name="DemoPayload",
            fields={
                "ok": GraphQLField(bool_type),
                "nested": GraphQLField(nested_type, resolve=lambda *_: object()),
            },
        ),
    )
    query_type = cast(
        "GraphQLObjectType",
        GraphQLObjectType(name="Query", fields={"_ping": GraphQLField(bool_type)}),
    )
    mutation_type = cast(
        "GraphQLObjectType",
        GraphQLObjectType(
            name="Mutation",
            fields={"DemoMutation": GraphQLField(payload_type, resolve=lambda *_: {"ok": True})},
        ),
    )
    return GraphQLSchema(query=query_type, mutation=mutation_type)


async def test_middleware_runs_status_checker_once_per_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production middleware fires for every resolved field in a mutation. We want to ensure
    that the BranchStatusChecker only runs once. This test runs the actual middleware against a
    mutation that resolves multiple nested fields and asserts the checker is invoked exactly once."""
    checker_instance = AsyncMock(spec=BranchStatusChecker)
    checker_factory = MagicMock(return_value=checker_instance)
    monkeypatch.setattr("infrahub.graphql.middleware.BranchStatusChecker", checker_factory)

    schema = _build_schema_with_nested_mutation()
    context = _FakeContext(db=object(), branch=_FakeBranch())

    result = await graphql(
        schema=schema,
        source="mutation { DemoMutation { ok nested { value } } }",
        context_value=context,
        middleware=[raise_on_mutation_for_branch_status],
    )

    assert result.errors is None
    assert result.data == {"DemoMutation": {"ok": True, "nested": {"value": "leaf"}}}
    # One checker constructed and `check()` awaited exactly once — even though the mutation
    # resolves four fields total (DemoMutation, ok, nested, value). The single `check()` call
    # also collapses what was previously two database queries (rebase + merge) into one.
    checker_factory.assert_called_once_with(db=context.db)
    checker_instance.check.assert_awaited_once_with(branch=context.branch, check_merge=True, check_needs_rebase=True)


async def test_middleware_does_not_run_status_checker_for_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Queries (as in not a mutation) should not trigger the status checker."""
    checker_factory = MagicMock(return_value=AsyncMock(spec=BranchStatusChecker))
    monkeypatch.setattr("infrahub.graphql.middleware.BranchStatusChecker", checker_factory)

    schema = _build_schema_with_nested_mutation()
    context = _FakeContext(db=object(), branch=_FakeBranch())

    result = await graphql(
        schema=schema,
        source="query { _ping }",
        context_value=context,
        middleware=[raise_on_mutation_for_branch_status],
    )

    assert result.errors is None
    checker_factory.assert_not_called()


async def test_middleware_skips_db_call_when_mutation_is_fully_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`BranchDelete` is on both allow-lists. The middleware should not call the checker in
    this case because no check is necessary."""
    checker_factory = MagicMock(return_value=AsyncMock(spec=BranchStatusChecker))
    monkeypatch.setattr("infrahub.graphql.middleware.BranchStatusChecker", checker_factory)

    bool_type = cast("GraphQLScalarType", GraphQLBoolean)
    query_type = cast(
        "GraphQLObjectType",
        GraphQLObjectType(name="Query", fields={"_ping": GraphQLField(bool_type)}),
    )
    mutation_type = cast(
        "GraphQLObjectType",
        GraphQLObjectType(
            name="Mutation",
            fields={"BranchDelete": GraphQLField(bool_type, resolve=lambda *_: True)},
        ),
    )
    schema = GraphQLSchema(query=query_type, mutation=mutation_type)
    context = _FakeContext(db=object(), branch=_FakeBranch())

    result = await graphql(
        schema=schema,
        source="mutation { BranchDelete }",
        context_value=context,
        middleware=[raise_on_mutation_for_branch_status],
    )

    assert result.errors is None
    checker_factory.assert_not_called()
