"""Where the Python setup flow may fail without taking the automations with it.

The flow reconciles the per-node automations in a ``finally``, so the reconcile runs even when the
submissions above it failed. That is only safe once this worker has confirmed the schema: the
reconcile deletes every automation missing from its gather, and a gather off a registry the worker
failed to refresh would delete automations that nothing else covers while the origin gate is on.

The order is what carries that, so the order is what is asserted, by reading the source.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from infrahub.computed_attribute import tasks

CONVERGENCE_WAIT = "wait_for_schema_to_converge"
RECONCILE = "_reconcile_python_computed_attribute_automations"


def _flow_body() -> ast.AsyncFunctionDef:
    source = textwrap.dedent(inspect.getsource(tasks.computed_attribute_setup_python.fn))
    parsed = ast.parse(source).body[0]
    assert isinstance(parsed, ast.AsyncFunctionDef)
    return parsed


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_the_convergence_wait_runs_before_the_reconcile_is_promised() -> None:
    """A worker that could not confirm the schema must not reach the reconcile at all."""
    tries = [node for node in ast.walk(_flow_body()) if isinstance(node, ast.Try)]
    assert len(tries) == 1

    assert CONVERGENCE_WAIT not in _called_names(tries[0]), (
        f"{CONVERGENCE_WAIT} sits inside the try, so its failure would still reconcile the "
        "automations from a registry this worker never refreshed"
    )
    assert CONVERGENCE_WAIT in _called_names(_flow_body())


def test_the_reconcile_survives_a_failed_submission() -> None:
    """The reconcile has to run when the recompute above it failed, which is why it is in a finally."""
    tries = [node for node in ast.walk(_flow_body()) if isinstance(node, ast.Try)]

    assert RECONCILE in _called_names(ast.Module(body=tries[0].finalbody, type_ignores=[]))
    assert RECONCILE not in _called_names(ast.Module(body=tries[0].body, type_ignores=[]))
