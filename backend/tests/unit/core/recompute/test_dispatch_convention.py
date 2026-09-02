from __future__ import annotations

import ast
import inspect

from infrahub.computed_attribute import tasks as computed_attribute_tasks


def _coalesced_argument(*, source: str, function: str) -> ast.expr:
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != function:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Name) or call.func.id != "build_bulk_recompute_dispatcher":
                continue
            for keyword in call.keywords:
                if keyword.arg == "coalesced":
                    return keyword.value
    raise AssertionError(f"{function} does not build a dispatcher with a coalesced argument")


def test_the_transform_flow_does_not_read_coalesced_off_the_node_ids() -> None:
    """Its three sibling flows infer the flag from ``object_ids``, and this one must not.

    A live refresh of a whole kind sends ids too, so inferring here would stamp those writes with
    the recompute origin and drive a chain from them. This flow is told which pass it belongs to.
    """
    argument = _coalesced_argument(source=inspect.getsource(computed_attribute_tasks), function="process_transform")

    assert "object_ids" not in ast.unparse(argument)
