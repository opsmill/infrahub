from __future__ import annotations

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
