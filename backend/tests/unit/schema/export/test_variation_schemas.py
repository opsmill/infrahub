from __future__ import annotations

from collections import Counter
from typing import Any

from tests.helpers.schema.export_variations import VARIATION_SCHEMAS, VariationSchema

from .conftest import load_on_new_baseline


def _defined_kinds(schema: dict[str, Any]) -> list[str]:
    return [
        f"{element['namespace']}{element['name']}"
        for element_type in ("generics", "nodes")
        for element in schema.get(element_type, [])
    ]


def test_variation_schema_loads_and_processes_on_an_empty_schema(variation_schema: VariationSchema) -> None:
    schema = variation_schema.payload()

    schema_branch = load_on_new_baseline(schema)

    assert {kind for kind in _defined_kinds(schema) if schema_branch.has(kind)} == set(_defined_kinds(schema))


def test_all_variation_schemas_load_and_process_together(all_variation_schemas: dict[str, Any]) -> None:
    schema_branch = load_on_new_baseline(all_variation_schemas)

    defined_kinds = _defined_kinds(all_variation_schemas)
    assert {kind for kind in defined_kinds if schema_branch.has(kind)} == set(defined_kinds)


def test_variation_schemas_have_distinct_kinds_and_namespaces() -> None:
    kind_counts = Counter(kind for variation in VARIATION_SCHEMAS for kind in _defined_kinds(variation.schema))
    namespaces_per_variation = [
        {
            element["namespace"]
            for element_type in ("generics", "nodes")
            for element in variation.schema.get(element_type, [])
        }
        for variation in VARIATION_SCHEMAS
    ]
    namespace_counts = Counter(namespace for namespaces in namespaces_per_variation for namespace in namespaces)

    assert [kind for kind, count in kind_counts.items() if count > 1] == []
    assert [namespace for namespace, count in namespace_counts.items() if count > 1] == []
    assert [len(namespaces) for namespaces in namespaces_per_variation] == [1] * len(VARIATION_SCHEMAS)
