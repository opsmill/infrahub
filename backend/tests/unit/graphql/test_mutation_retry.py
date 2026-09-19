from __future__ import annotations

import ast
import inspect

from infrahub.graphql.mutations import main

MIXIN_NAME = "InfrahubMutationMixin"

# The create retry sits on an inner helper rather than on the mutation entrypoint, because the
# retried scope has to stop at the creation transaction: replaying anything that runs after that
# transaction commits would create a second node instead of retrying the first one.
EXPECTED_RETRY_LABELS = {
    "_create_object_with_retry": "object_create",
    "mutate_update": "object_update",
    "mutate_upsert": "object_upsert",
    "mutate_delete": "object_delete",
}


def _retry_label(method: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for decorator in method.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "retry_db_transaction"
        ):
            continue
        for keyword in decorator.keywords:
            if (
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                return keyword.value.value
    return None


def test_crud_mutations_carry_a_retry_decorator() -> None:
    """Guard against a refactor silently dropping a retry decorator from a CRUD mutation.

    Only the presence and the metric label of the decorators are checked here; the retry
    behaviour itself is covered where the decorator is defined.
    """
    class_defs = [
        node
        for node in ast.parse(inspect.getsource(main)).body
        if isinstance(node, ast.ClassDef) and node.name == MIXIN_NAME
    ]
    assert len(class_defs) == 1, f"Expected exactly one {MIXIN_NAME} class definition, found {len(class_defs)}"

    methods = [node for node in class_defs[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    retry_labels = {method.name: label for method in methods if (label := _retry_label(method)) is not None}

    assert retry_labels == EXPECTED_RETRY_LABELS
