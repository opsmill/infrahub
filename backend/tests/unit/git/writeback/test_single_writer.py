from __future__ import annotations

import ast
import re
from pathlib import Path

import infrahub

INFRAHUB_PACKAGE = Path(infrahub.__file__).parent

DELIVERY_ATTRIBUTE_NAMES: tuple[str, ...] = (
    "delivery_status",
    "delivery_failure_cause",
    "delivery_error",
    "delivery_queue",
    "delivery_held_regeneration",
    "delivery_last_abandonment",
    "delivery_last_delivered_commit",
    "delivery_reverted",
    "delivery_progress",
)

STORE_MODULE = "git/writeback/store.py"
STORE_IMPORT_PATH = "infrahub.git.writeback.store"
SCHEMA_DEFINITION_MODULE = "core/schema/definitions/core/repository.py"
GENERATED_PROTOCOLS_MODULE = "core/protocols.py"

# A filter key such as `delivery_status__value` names the attribute as well.
NAMED_ATTRIBUTE = re.compile(rf"(?<!\w)({'|'.join(DELIVERY_ATTRIBUTE_NAMES)})(?:__\w+)?(?!\w)")


def _attribute_names_by_module() -> dict[str, list[tuple[int, str]]]:
    named: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(INFRAHUB_PACKAGE.rglob("*.py")):
        module = path.relative_to(INFRAHUB_PACKAGE).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in NAMED_ATTRIBUTE.finditer(line):
                named.setdefault(module, []).append((line_number, match.group(1)))
    return named


def test_only_the_store_names_the_delivery_attributes() -> None:
    """The store is the one writer of the delivery state, so another module that names an attribute bypasses it."""
    named = _attribute_names_by_module()

    assert {name for _, name in named.get(SCHEMA_DEFINITION_MODULE, [])} == set(DELIVERY_ATTRIBUTE_NAMES)

    allowed = {STORE_MODULE, SCHEMA_DEFINITION_MODULE, GENERATED_PROTOCOLS_MODULE}
    violations = [
        f"infrahub/{module}:{line_number} names {name}"
        for module, occurrences in named.items()
        if module not in allowed
        for line_number, name in occurrences
    ]
    assert not violations, "Only the delivery state store may name a delivery attribute of CoreRepository:\n" + (
        "\n".join(violations)
    )


def _absolute_module(*, module: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = ["infrahub", *module.removesuffix(".py").split("/")][: -node.level]
    return ".".join([*package, *([node.module] if node.module else [])])


def _private_store_names_used_by(*, module: str, tree: ast.Module) -> list[str]:
    store_names = set()
    used: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_from = _absolute_module(module=module, node=node)
            for alias in node.names:
                if imported_from == STORE_IMPORT_PATH and alias.name.startswith("_"):
                    used.append(f"infrahub/{module}:{node.lineno} imports {alias.name}")
                if f"{imported_from}.{alias.name}" == STORE_IMPORT_PATH:
                    store_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            store_names |= {alias.asname or alias.name for alias in node.names if alias.name == STORE_IMPORT_PATH}
    used.extend(
        f"infrahub/{module}:{node.lineno} uses {node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr.startswith("_") and ast.unparse(node.value) in store_names
    )
    return used


def test_only_the_store_uses_its_private_names() -> None:
    """The store keeps the attribute names private, so a module that reaches them writes around the store."""
    violations = [
        violation
        for path in sorted(INFRAHUB_PACKAGE.rglob("*.py"))
        if (module := path.relative_to(INFRAHUB_PACKAGE).as_posix()) != STORE_MODULE
        for violation in _private_store_names_used_by(module=module, tree=ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert not violations, "Only the delivery state store may use its private names:\n" + "\n".join(violations)
