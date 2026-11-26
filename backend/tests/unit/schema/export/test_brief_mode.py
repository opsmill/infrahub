from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from structlog.testing import capture_logs

from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.manager import SchemaManager
from infrahub.schema.export.exporter import SchemaExporter, build_core_schema_baseline
from infrahub.schema.export.models import SchemaExportMode
from tests.helpers.schema.export_variations import DEPRECATED_VALIDATION_FIELDS, NUMBER_POOL_RANGES

from .conftest import ROUND_TRIP_BRANCH_NAME, load_on_new_baseline

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from infrahub.core.schema.schema_branch import SchemaBranch

WARNING_LOG_LEVEL = "warning"
REPEATED_EXPORTS = 3


def _device_schema(**node_fields: Any) -> dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Device",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                **node_fields,
            }
        ],
    }


def _warnings(records: list[MutableMapping[str, Any]]) -> list[MutableMapping[str, Any]]:
    return [record for record in records if record["log_level"] == WARNING_LOG_LEVEL]


def test_export_ends_and_logs_the_differences_processing_cannot_remove(schema_exporter: SchemaExporter) -> None:
    source = load_on_new_baseline(_device_schema())
    stored_node = source.get_node(name="TestingDevice", duplicate=False)
    stored_node.label = None
    stored_node.get_attribute(name="description").label = None

    with capture_logs() as records:
        document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.BRIEF, namespaces=None)

    assert document.model_dump(exclude_unset=True)["nodes"] == [
        {
            "name": "Device",
            "namespace": "Testing",
            "human_friendly_id": ["name__value"],
            "uniqueness_constraints": [["name__value"]],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        }
    ]
    assert [(warning["branch"], warning["differences"]) for warning in _warnings(records)] == [
        (
            ROUND_TRIP_BRANCH_NAME,
            [
                {"kind": "TestingDevice", "element": None, "field": "label"},
                {"kind": "TestingDevice", "element": "description", "field": "label"},
            ],
        )
    ]


def _exporter_with_generic_in_baseline(namespace: str, name: str) -> SchemaExporter:
    def build_baseline(branch_name: str) -> SchemaBranch:
        baseline = build_core_schema_baseline(branch_name)
        baseline.load_schema(
            schema=SchemaRoot(
                generics=[{"name": name, "namespace": namespace, "attributes": [{"name": "name", "kind": "Text"}]}]
            )
        )
        return baseline

    return SchemaExporter(baseline_factory=build_baseline)


def test_export_returns_the_full_document_when_processing_rejects_the_candidate(
    schema_exporter: SchemaExporter,
) -> None:
    source = load_on_new_baseline(_device_schema())
    rejecting_exporter = _exporter_with_generic_in_baseline(namespace="Testing", name="Device")

    with capture_logs() as records:
        document = rejecting_exporter.export(schema_branch=source, mode=SchemaExportMode.BRIEF, namespaces=None)

    full_document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.FULL, namespaces=None)
    assert document.model_dump(exclude_unset=True) == full_document.model_dump(exclude_unset=True)
    assert [(warning["branch"], warning["error"]) for warning in _warnings(records)] == [
        (
            ROUND_TRIP_BRANCH_NAME,
            "TestingDevice already exist in the schema as a Generic. Either rename it or delete the existing one.",
        )
    ]


def test_export_returns_the_full_document_when_the_stored_schema_fails_validation(
    schema_exporter: SchemaExporter,
) -> None:
    source = build_core_schema_baseline(ROUND_TRIP_BRANCH_NAME)
    source.load_schema(schema=SchemaRoot(**_device_schema(display_label="{{ missing__value }}")))
    source.process(validate_schema=False)

    with capture_logs() as records:
        document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.BRIEF, namespaces=None)

    full_document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.FULL, namespaces=None)
    assert document.model_dump(exclude_unset=True) == full_document.model_dump(exclude_unset=True)
    assert [(warning["branch"], warning["error"]) for warning in _warnings(records)] == [
        (ROUND_TRIP_BRANCH_NAME, "TestingDevice.display_label: missing__value is invalid on schema TestingDevice")
    ]


@pytest.fixture
def registry_schema_branch(monkeypatch: pytest.MonkeyPatch, all_variation_schemas: dict[str, Any]) -> SchemaBranch:
    """The branch schema of a schema registry that holds the core schema and every variation schema."""
    monkeypatch.setattr(registry, "_schema", SchemaManager())
    schema_branch = registry.schema.get_schema_branch(name=ROUND_TRIP_BRANCH_NAME)
    for definitions in (internal_schema, core_models, deprecated_models, all_variation_schemas):
        schema_branch.load_schema(schema=SchemaRoot(**definitions))
    schema_branch.process()
    registry.schema.set_schema_branch(name=ROUND_TRIP_BRANCH_NAME, schema=schema_branch)
    return registry.schema.get_schema_branch(name=ROUND_TRIP_BRANCH_NAME)


def _user_kinds(schema_branch: SchemaBranch, core_schema_kinds: frozenset[str]) -> list[str]:
    return sorted((set(schema_branch.nodes) | set(schema_branch.generics)) - core_schema_kinds)


def test_exports_keep_no_schema_and_leave_the_schema_cache_unchanged(
    schema_exporter: SchemaExporter, registry_schema_branch: SchemaBranch
) -> None:
    cache_size = len(registry_schema_branch._cache)

    for _ in range(REPEATED_EXPORTS):
        schema_exporter.export(schema_branch=registry_schema_branch, mode=SchemaExportMode.BRIEF, namespaces=None)

    assert len(registry.schema.get_schema_branch(name=ROUND_TRIP_BRANCH_NAME)._cache) == cache_size
    assert vars(schema_exporter) == {"_baseline_factory": build_core_schema_baseline}


def test_exports_leave_the_branch_schema_unchanged(
    schema_exporter: SchemaExporter, registry_schema_branch: SchemaBranch, core_schema_kinds: frozenset[str]
) -> None:
    user_kinds = _user_kinds(registry_schema_branch, core_schema_kinds)
    converted_kinds = {
        f"{node['namespace']}{node['name']}"
        for variation in (DEPRECATED_VALIDATION_FIELDS, NUMBER_POOL_RANGES)
        for node in variation.schema["nodes"]
    }
    schema_hash = registry_schema_branch.get_hash()
    dumps = {kind: registry_schema_branch.get(name=kind, duplicate=False).model_dump() for kind in user_kinds}

    for mode in (SchemaExportMode.BRIEF, SchemaExportMode.FULL):
        schema_exporter.export(schema_branch=registry_schema_branch, mode=mode, namespaces=None)

    schema_branch = registry.schema.get_schema_branch(name=ROUND_TRIP_BRANCH_NAME)
    assert converted_kinds <= set(user_kinds)
    assert schema_branch.get_hash() == schema_hash
    assert {kind: schema_branch.get(name=kind, duplicate=False).model_dump() for kind in user_kinds} == dumps
