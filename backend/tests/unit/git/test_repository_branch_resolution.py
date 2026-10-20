"""The Infrahub branch each flow hands to the repository factory.

Omitting the branch fails loudly at call time, but passing the wrong one does not: a repository whose
default branch is not Infrahub's own would simply be read on the wrong branch. These pin the
expression each call site forwards.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute import tasks as computed_attribute_tasks
from infrahub.generators import tasks as generator_tasks
from infrahub.webhook import models as webhook_models

if TYPE_CHECKING:
    from types import ModuleType


def find_keyword(module: ModuleType, function_name: str, callee: str, keyword: str) -> str:
    """Return the source of one keyword argument of a call inside a named function.

    Raises:
        AssertionError: When the function, the call or the keyword cannot be found.

    """
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) or node.name != function_name:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if called != callee:
                continue
            for word in call.keywords:
                if word.arg == keyword:
                    return ast.unparse(word.value)
    raise AssertionError(f"No {callee}(...) call with a {keyword}= argument inside {function_name}")


@dataclass
class BranchArgumentCase:
    name: str
    module: ModuleType
    function_name: str
    callee: str
    expected: str


BRANCH_ARGUMENT_CASES = [
    BranchArgumentCase(
        name="generator_flow",
        module=generator_tasks,
        function_name="run_generator",
        callee="get_initialized_repo",
        expected="model.branch_name",
    ),
    BranchArgumentCase(
        name="computed_attribute_flow",
        module=computed_attribute_tasks,
        function_name="process_transform",
        callee="get_initialized_repo",
        expected="branch_name",
    ),
]


@pytest.mark.parametrize("case", BRANCH_ARGUMENT_CASES, ids=[case.name for case in BRANCH_ARGUMENT_CASES])
def test_flow_forwards_its_own_infrahub_branch(case: BranchArgumentCase) -> None:
    forwarded = find_keyword(
        module=case.module,
        function_name=case.function_name,
        callee=case.callee,
        keyword="infrahub_branch_name",
    )

    assert forwarded == case.expected


def test_transform_webhook_resolves_an_infrahub_branch_not_the_repository_default() -> None:
    """The webhook's branch is an Infrahub branch; the repository's own default branch is a remote one.

    Reading the latter here names a branch that need not exist in Infrahub at all.
    """
    source = inspect.getsource(webhook_models.TransformWebhook.compute_payload)

    assert "context.branch or registry.default_branch" in source
    assert "repo.default_branch" not in source
