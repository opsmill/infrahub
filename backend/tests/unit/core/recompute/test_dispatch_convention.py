from __future__ import annotations

import ast
import inspect
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute import tasks as computed_attribute_tasks
from infrahub.display_labels import tasks as display_label_tasks
from infrahub.hfid import tasks as hfid_tasks

if TYPE_CHECKING:
    from types import ModuleType

# Dropping either one makes the dispatch write with the live origin and start no chained level,
# which silently leaves every value below that level stale.
CHAIN_ARGUMENTS = ("coalesced", "recompute_depth")

DISPATCHING_MODULES = [computed_attribute_tasks, display_label_tasks, hfid_tasks]


def _dispatch_calls(module: ModuleType) -> list[ast.Call]:
    tree = ast.parse(inspect.getsource(module))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dispatch"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "dispatcher"
    ]


@pytest.mark.parametrize("module", DISPATCHING_MODULES, ids=[module.__name__ for module in DISPATCHING_MODULES])
def test_every_bulk_recompute_dispatch_passes_the_chain_arguments(module: ModuleType) -> None:
    calls = _dispatch_calls(module)
    assert len(calls) >= 1

    missing = [
        f"{module.__name__}:{call.lineno} does not pass {argument}"
        for call in calls
        for argument in CHAIN_ARGUMENTS
        if argument not in {keyword.arg for keyword in call.keywords}
    ]
    assert missing == []
