from __future__ import annotations

import ast
import inspect
import textwrap
from typing import TYPE_CHECKING, TypeGuard

import pytest

from infrahub.services import InfrahubServices
from infrahub.workers.utils import has_parameter
from infrahub.workflows.catalogue import get_workflows

if TYPE_CHECKING:
    from infrahub.workflows.models import WorkflowDefinition

_SESSION_OPENERS = ("start_session", "start_transaction")


def _is_service_database(node: ast.AST) -> TypeGuard[ast.Attribute]:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "database"
        and isinstance(node.value, ast.Name)
        and node.value.id == "service"
    )


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _scan_flow(workflow: WorkflowDefinition) -> list[str]:
    flow = workflow.load_function()
    if not has_parameter(func=flow, types=[InfrahubServices.__name__, InfrahubServices]):
        return []

    lines, source_start = inspect.getsourcelines(flow.fn)
    tree = ast.parse(textwrap.dedent("".join(lines)))
    parents = _build_parent_map(tree)

    violations: list[str] = []
    for node in ast.walk(tree):
        if not _is_service_database(node):
            continue
        parent = parents[node]
        if isinstance(parent, ast.Attribute) and parent.attr in _SESSION_OPENERS:
            continue
        lineno = source_start + node.lineno - 1
        violations.append(f"{workflow.module}:{lineno} flow={workflow.function!r} -> {ast.unparse(parent)}")
    return violations


@pytest.mark.parametrize(
    "workflow",
    [pytest.param(workflow, id=workflow.name) for workflow in get_workflows()],
)
def test_flow_does_not_reuse_shared_database_session(workflow: WorkflowDefinition) -> None:
    """Prefect flows that take a `service: InfrahubServices` parameter must access
    `service.database` only through `.start_session(` or `.start_transaction(`.

    Passing `service.database` directly (e.g. `db=service.database`) reuses the
    worker's shared neo4j async session and triggers
    `RuntimeError: read() called while another coroutine is already waiting for incoming data`
    when concurrent flows execute. Each flow must scope its own session.

    Aliasing (`database = service.database`) also fails this check on purpose:
    inline `service.database.start_session(...)` is the required form so the
    convention stays mechanically verifiable.
    """
    violations = _scan_flow(workflow=workflow)
    assert not violations, "Flow accesses service.database without opening a session:\n" + "\n".join(violations)
