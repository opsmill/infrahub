"""Where the Python setup flow may fail without taking the automations with it.

The flow reconciles the per-node automations in a ``finally``, so the reconcile runs even when the
submissions above it failed. The reconcile deletes every automation missing from its gather, so the
schema refresh has to come first: a gather off a registry this worker never refreshed would delete
automations that nothing else covers while the origin gate is on.

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


def _called_name(call: ast.Call) -> str | None:
    return call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", None)


def _positions(name: str, node: ast.AST) -> list[int]:
    """Where ``name`` is awaited. An unawaited call never runs, so it does not count as ordering."""
    return sorted(
        child.lineno
        for child in ast.walk(node)
        if isinstance(child, ast.Await) and isinstance(child.value, ast.Call) and _called_name(child.value) == name
    )


def _reconciling_try(body: ast.AST) -> ast.Try:
    """The try whose finally reconciles, found by what it does rather than by being the only one."""
    tries = [
        node
        for node in ast.walk(body)
        if isinstance(node, ast.Try) and RECONCILE in _called_names(ast.Module(body=node.finalbody, type_ignores=[]))
    ]
    assert len(tries) == 1, "exactly one try reconciles the automations in its finally"
    return tries[0]


def _called_names(node: ast.AST) -> set[str]:
    return {
        called
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and (called := _called_name(child)) is not None
    }


def test_the_schema_refresh_runs_before_the_reconcile_is_promised() -> None:
    """The refresh has to be behind the flow, not inside the block that promises a reconcile."""
    body = _flow_body()
    reconciling_try = _reconciling_try(body)

    waits = _positions(CONVERGENCE_WAIT, body)
    assert len(waits) == 1, f"{CONVERGENCE_WAIT} is awaited once"
    assert waits[0] < reconciling_try.lineno, (
        f"{CONVERGENCE_WAIT} runs at or after the try that promises the reconcile, so a failure "
        "reaching it would still reconcile from a registry this worker never refreshed"
    )


def test_the_reconcile_survives_a_failed_submission() -> None:
    """The reconcile has to run when the recompute above it failed, which is why it is in a finally."""
    reconciling_try = _reconciling_try(_flow_body())

    assert RECONCILE not in _called_names(ast.Module(body=reconciling_try.body, type_ignores=[]))
