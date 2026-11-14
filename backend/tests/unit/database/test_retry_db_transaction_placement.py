from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import dataclass
from typing import Any, Callable

import pytest

from infrahub.core.regeneration.impact import FieldLevelImpactResolver
from infrahub.core.validators import tasks as validator_tasks
from infrahub.proposed_change import tasks as proposed_change_tasks


@dataclass
class RetryPlacementCase:
    name: str
    function: Callable[..., Any]
    retry_name: str


def _retry_names(function: Callable[..., Any]) -> list[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    definition = tree.body[0]
    assert isinstance(definition, ast.AsyncFunctionDef)
    names: list[str] = []
    for decorator in definition.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "retry_db_transaction"
        ):
            continue
        names.extend(
            str(keyword.value.value)
            for keyword in decorator.keywords
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant)
        )
    return names


RETRY_PLACEMENT_CASES = [
    RetryPlacementCase(
        name="field_level_impact_resolve",
        function=FieldLevelImpactResolver.resolve,
        retry_name="field_level_impact_resolve",
    ),
    RetryPlacementCase(
        name="constraint_check",
        function=validator_tasks._check_constraint,
        retry_name="schema_path_validate",
    ),
    RetryPlacementCase(
        name="proposed_change_diff_update",
        function=proposed_change_tasks._update_proposed_change_diff,
        retry_name="proposed_change_diff_update",
    ),
    RetryPlacementCase(
        name="schema_integrity_constraints",
        function=proposed_change_tasks._get_proposed_change_schema_integrity_constraints,
        retry_name="schema_integrity_constraints",
    ),
    RetryPlacementCase(
        name="schema_integrity_conflicted_fields",
        function=proposed_change_tasks._get_conflicted_fields,
        retry_name="schema_integrity_conflicted_fields",
    ),
    RetryPlacementCase(
        name="schema_integrity_record",
        function=proposed_change_tasks._record_schema_integrity_conflicts,
        retry_name="schema_integrity_record",
    ),
]


@pytest.mark.parametrize("case", RETRY_PLACEMENT_CASES, ids=lambda case: case.name)
def test_database_work_of_proposed_change_checks_is_retried(case: RetryPlacementCase) -> None:
    assert _retry_names(case.function) == [case.retry_name]
