from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import TypeGuard

import pytest

from infrahub.graphql.schema import InfrahubBaseQuery
from infrahub.proposed_change import action_checker

_CONTEXT_NAMES = ("graphql_context", "context")
_ALLOWED_DATABASE_ATTRIBUTES = ("start_session", "schema")
# Modules outside a resolver's own module that receive the whole GraphQL context from a query resolver.
_CONTEXT_HELPER_MODULES = (action_checker.__name__,)


def _root_query_resolver_modules() -> dict[str, str]:
    modules: dict[str, str] = {}
    for field_name, field in InfrahubBaseQuery._meta.fields.items():
        resolver = field.resolver or getattr(InfrahubBaseQuery, f"resolve_{field_name}", None)
        if resolver is None:
            raise AssertionError(f"Root query field {field_name!r} has no resolver to scan")
        modules[field_name] = resolver.__module__
    return modules


def _scanned_module_names() -> list[str]:
    return sorted({*_root_query_resolver_modules().values(), *_CONTEXT_HELPER_MODULES})


def _is_context_database(node: ast.AST) -> TypeGuard[ast.Attribute]:
    if not isinstance(node, ast.Attribute) or node.attr != "db":
        return False
    base = node.value
    if isinstance(base, ast.Name):
        return base.id in _CONTEXT_NAMES
    return isinstance(base, ast.Attribute) and base.attr == "context"


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _scan_module(module_name: str) -> list[str]:
    module = importlib.import_module(module_name)
    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    parents = _build_parent_map(tree)

    violations: list[str] = []
    for node in ast.walk(tree):
        if not _is_context_database(node):
            continue
        parent = parents[node]
        if isinstance(parent, ast.Attribute) and parent.attr in _ALLOWED_DATABASE_ATTRIBUTES:
            continue
        violations.append(f"{module_name}:{node.lineno} -> {ast.unparse(parent)}")
    return violations


@pytest.mark.parametrize(
    "module_name",
    [pytest.param(module_name, id=module_name) for module_name in _scanned_module_names()],
)
def test_query_resolver_does_not_reuse_request_database_session(module_name: str) -> None:
    """The module of every root query field's resolver must access the GraphQL context database only through `.start_session(` or `.schema`.

    The context database holds the one session of the whole request, and graphql-core resolves query root fields
    concurrently, so two resolvers reading through it share one connection and fail with
    `RuntimeError: read() called while another coroutine is already waiting for incoming data`.

    Aliasing (`db = graphql_context.db`) also fails this check on purpose: the inline
    `graphql_context.db.start_session(...)` form keeps the convention mechanically verifiable.
    """
    violations = _scan_module(module_name=module_name)
    assert not violations, "Resolver reads the request database session directly:\n" + "\n".join(violations)
