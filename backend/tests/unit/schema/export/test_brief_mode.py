from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from structlog.testing import capture_logs

from infrahub import __version__
from infrahub.core.constants import RESTRICTED_NAMESPACES, InfrahubKind
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.basenode_schema import AttributePathParsingError
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.node_inheritance_handler import PROPERTIES_INHERITED_FROM_GENERIC
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import SchemaNotFoundError
from infrahub.schema.export.exporter import SchemaExporter, build_core_schema_baseline, is_generated_relationship
from infrahub.schema.export.models import SchemaExportMode
from tests.helpers.schema.export_variations import (
    ATTRIBUTE_SETTINGS,
    DEPRECATED_VALIDATION_FIELDS,
    DERIVED_FROM_UNIQUE_ATTRIBUTE,
    INHERITED_PROPERTIES,
    NUMBER_POOL_RANGES,
    VariationSchema,
)

from .conftest import (
    OTHER_NAMESPACE,
    ROUND_TRIP_BRANCH_NAME,
    SELECTED_NAMESPACE,
    NamespaceFilterExports,
    RoundTrip,
    elements_in_namespace,
    load_on_new_baseline,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, MutableMapping

WARNING_LOG_LEVEL = "warning"
REPEATED_EXPORTS = 3
EXPECTED_FILE_FORMAT_VERSION = "1.0"
EXPORTER_WARNING_KEYS = {"error", "differences"}
"""Keys of the warnings the export logs when it reaches the fallback or when differences remain."""


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


@dataclass
class ProcessingErrorCase:
    name: str
    error: Exception
    message: str


PROCESSING_ERROR_CASES = [
    ProcessingErrorCase(
        name="schema-not-found",
        error=SchemaNotFoundError(branch_name=ROUND_TRIP_BRANCH_NAME, identifier="TestingSite", message="no site"),
        message="\n        no site\n        main | TestingSite\n        ",
    ),
    ProcessingErrorCase(name="path-parsing", error=AttributePathParsingError("bad path"), message="bad path"),
]


class _ProcessingFailsSchemaBranch(SchemaBranch):
    """A baseline whose processing raises the given error, as processing a reduced candidate can."""

    def __init__(self, name: str, error: Exception) -> None:
        super().__init__(cache={}, name=name)
        self._error = error

    def process(self, validate_schema: bool = True, default_branch_schema: SchemaBranch | None = None) -> None:
        raise self._error


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in PROCESSING_ERROR_CASES])
def test_export_returns_the_full_document_when_processing_the_candidate_raises(
    schema_exporter: SchemaExporter, case: ProcessingErrorCase
) -> None:
    source = load_on_new_baseline(_device_schema())
    failing_exporter = SchemaExporter(
        baseline_factory=lambda name: _ProcessingFailsSchemaBranch(name=name, error=case.error)
    )

    with capture_logs() as records:
        document = failing_exporter.export(schema_branch=source, mode=SchemaExportMode.BRIEF, namespaces=None)

    full_document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.FULL, namespaces=None)
    assert document.model_dump(exclude_unset=True) == full_document.model_dump(exclude_unset=True)
    assert [(warning["branch"], warning["error"]) for warning in _warnings(records)] == [
        (ROUND_TRIP_BRANCH_NAME, case.message)
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


def _keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _declared_kinds(variation: VariationSchema) -> set[str]:
    return {
        f"{element['namespace']}{element['name']}"
        for element in variation.schema.get("nodes", []) + variation.schema.get("generics", [])
    }


def _exported_elements(exported: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f"{element['namespace']}{element['name']}": element for element in exported["nodes"] + exported["generics"]}


def _exporter_warnings(records: list[MutableMapping[str, Any]]) -> list[MutableMapping[str, Any]]:
    return [warning for warning in _warnings(records) if EXPORTER_WARNING_KEYS & warning.keys()]


def _brief_export(schema_exporter: SchemaExporter, variation: VariationSchema) -> dict[str, dict[str, Any]]:
    source = load_on_new_baseline(variation.payload())
    document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.BRIEF, namespaces=None)
    return _exported_elements(document.model_dump(exclude_unset=True))


def test_brief_export_loads_to_the_same_schema_without_the_fallback(
    variation_schema: VariationSchema, schema_round_trip: RoundTrip
) -> None:
    with capture_logs() as records:
        document = schema_round_trip(variation_schema.payload(), SchemaExportMode.BRIEF)

    exported = document.model_dump(exclude_unset=True)
    source = load_on_new_baseline(variation_schema.payload())
    elements = _exported_elements(exported)

    assert _exporter_warnings(records) == []
    assert (exported["version"], exported["infrahub_version"]) == (EXPECTED_FILE_FORMAT_VERSION, __version__)
    assert "id" not in set(_keys(exported))
    assert set(elements) == _declared_kinds(variation_schema)
    assert InfrahubKind.IPNAMESPACE not in elements
    assert [kind for kind, element in elements.items() if element["namespace"] in RESTRICTED_NAMESPACES] == []
    for kind, element in elements.items():
        stored = source.get(name=kind, duplicate=False)
        stored_attributes = [
            stored.get_attribute(name=attribute["name"]) for attribute in element.get("attributes", [])
        ]
        stored_relationships = [
            stored.get_relationship(name=relationship["name"]) for relationship in element.get("relationships", [])
        ]
        assert [attribute.name for attribute in stored_attributes if attribute.inherited] == []
        assert [relationship.name for relationship in stored_relationships if relationship.inherited] == []
        assert [
            relationship.name
            for relationship in stored_relationships
            if is_generated_relationship(relationship.model_dump())
        ] == []


def test_brief_export_writes_the_properties_a_node_took_from_its_generic(schema_exporter: SchemaExporter) -> None:
    router = _brief_export(schema_exporter, INHERITED_PROPERTIES)["PinnedRouter"]

    assert {name: router.get(name) for name in PROPERTIES_INHERITED_FROM_GENERIC} == {
        "human_friendly_id": ["name__value"],
        "display_label": "name__value",
        "display_labels": ["name__value"],
        "default_filter": "name__value",
        "menu_placement": "PinnedRack",
        "uniqueness_constraints": [["name__value"]],
        "icon": "mdi:router",
        "order_by": ["name__value"],
    }


def test_brief_export_leaves_out_a_label_equal_to_the_derived_label(schema_exporter: SchemaExporter) -> None:
    item = _brief_export(schema_exporter, ATTRIBUTE_SETTINGS)["DetailItem"]

    assert item["label"] == "Detail item"
    assert item["attributes"][0] == {"name": "name", "kind": "Text", "unique": True}


def test_brief_export_writes_a_unique_attribute_without_the_values_derived_from_it(
    schema_exporter: SchemaExporter,
) -> None:
    device = _brief_export(schema_exporter, DERIVED_FROM_UNIQUE_ATTRIBUTE)["DerivedDevice"]

    assert device["attributes"] == [{"name": "name", "kind": "Text", "unique": True}]
    assert "human_friendly_id" not in device
    assert "uniqueness_constraints" not in device


def test_brief_export_writes_validation_settings_only_under_parameters(schema_exporter: SchemaExporter) -> None:
    hostname, notes, aliases = _brief_export(schema_exporter, DEPRECATED_VALIDATION_FIELDS)["LegacyHost"]["attributes"]

    assert hostname == {
        "name": "hostname",
        "kind": "Text",
        "unique": True,
        "parameters": {"regex": "^[a-z0-9-]+$", "min_length": 3, "max_length": 32},
    }
    assert notes == {
        "name": "notes",
        "kind": "TextArea",
        "optional": True,
        "parameters": {"regex": "^[^<>]*$", "min_length": 1, "max_length": 500},
    }
    # The parameters of a List attribute have no length settings, so those stay at the top level.
    assert "regex" not in aliases
    assert aliases["parameters"] == {"regex": "^[a-z0-9-]+$"}


def test_brief_export_writes_number_pool_bounds_only_as_ranges(schema_exporter: SchemaExporter) -> None:
    attributes = _brief_export(schema_exporter, NUMBER_POOL_RANGES)["PoolCircuit"]["attributes"]

    assert {attribute["name"]: attribute.get("parameters") for attribute in attributes} == {
        "name": None,
        "vlan_id": {"ranges": [{"start": 100, "end": 200}]},
        "vni": {"ranges": [{"start": 5000}]},
        "circuit_index": {
            "ranges": [{"start": 1, "end": 50, "weight": 10}, {"start": 51, "end": 100}],
            "allocation_scope": ["site"],
        },
    }


def test_brief_export_of_one_namespace_holds_its_entries_as_in_the_unfiltered_export(
    export_with_and_without_filter: NamespaceFilterExports,
) -> None:
    with capture_logs() as records:
        filtered, unfiltered = export_with_and_without_filter(SchemaExportMode.BRIEF, [SELECTED_NAMESPACE])

    assert _exporter_warnings(records) == []
    assert _exported_elements(unfiltered).keys() == {"NetworkDevice", "NetworkEndpoint", "LocationSite"}
    assert _exported_elements(filtered).keys() == {"NetworkDevice", "NetworkEndpoint"}
    assert {name: filtered[name] for name in ("nodes", "generics")} == elements_in_namespace(
        unfiltered, SELECTED_NAMESPACE
    )
    assert [
        relationship["peer"] for relationship in _exported_elements(filtered)["NetworkDevice"]["relationships"]
    ] == [f"{OTHER_NAMESPACE}Site"]
