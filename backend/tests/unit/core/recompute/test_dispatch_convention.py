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

# A dispatcher built without `coalesced` writes with the live origin and drives no chained level,
# which silently leaves every value below that level stale.
BUILD_ARGUMENT = "coalesced"
DISPATCH_ARGUMENT = "recompute_depth"

DISPATCHING_MODULES = [computed_attribute_tasks, display_label_tasks, hfid_tasks]


def _calls_named(module: ModuleType, name: str) -> list[ast.Call]:
    tree = ast.parse(inspect.getsource(module))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == name) or (isinstance(func, ast.Attribute) and func.attr == name):
            found.append(node)
    return found


@pytest.mark.parametrize("module", DISPATCHING_MODULES, ids=[module.__name__ for module in DISPATCHING_MODULES])
def test_every_bulk_recompute_flow_passes_the_chain_arguments(module: ModuleType) -> None:
    builds = _calls_named(module, "build_bulk_recompute_dispatcher")
    dispatches = _calls_named(module, "dispatch")
    assert len(builds) >= 1
    assert len(dispatches) >= 1

    missing = [
        f"{module.__name__}:{call.lineno} does not pass {argument}"
        for call, argument in [
            *((call, BUILD_ARGUMENT) for call in builds),
            *((call, DISPATCH_ARGUMENT) for call in dispatches),
        ]
        if argument not in {keyword.arg for keyword in call.keywords}
    ]
    assert missing == []
