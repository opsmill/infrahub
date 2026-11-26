from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.schema.generated.write import (
    AttributeSchemaWrite,
    GenericSchemaWrite,
    NodeSchemaWrite,
    RelationshipSchemaWrite,
)
from pydantic import BaseModel, TypeAdapter

from infrahub.core.constants import RelationshipKind
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.schema.export.exporter import SchemaExporter, build_core_schema_baseline
from infrahub.schema.export.models import SchemaExportMode
from tests.helpers.schema.export_variations import (
    DEPRECATED_VALIDATION_FIELDS,
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
    from infrahub.core.schema.schema_branch import SchemaBranch

GENERATED_RELATIONSHIP_KINDS = {
    RelationshipKind.GROUP,
    RelationshipKind.PROFILE,
    RelationshipKind.HIERARCHY,
    RelationshipKind.TEMPLATE,
}
NOT_EXPORTED_FIELDS = {"id", "attributes", "relationships", "parameters"}
DEPRECATED_ATTRIBUTE_FIELDS = {"regex", "min_length", "max_length"}
"""Top-level attribute fields that a schema file holds in `parameters` instead."""

DEPRECATED_PARAMETER_FIELDS = {"start_range", "end_range"}
"""NumberPool parameters that a schema file holds as one entry of `ranges` instead."""

PRESENT_STATE = "present"

LabelledSchema = dict[str, Any]


def _valued_fields(model: type[BaseModel], stored: dict[str, Any], skipped: set[str]) -> dict[str, Any]:
    """Return the fields of the write model that hold a value in the dump of a stored element.

    The values are read through the write model, so a nested value holds only what a schema file can carry.
    """
    valued = {name: value for name, value in stored.items() if name in model.model_fields and name not in skipped}
    written = model.model_validate(valued).model_dump(exclude_none=True)
    return {name: written[name] for name, value in valued.items() if value is not None}


def _missing_values(exported: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in expected.items() if exported.get(name) != value}


def _attribute_models(attribute: dict[str, Any]) -> tuple[type[BaseModel], type[BaseModel] | None]:
    """Return the write model of a stored attribute and the write model of its parameters."""
    model = TypeAdapter(AttributeSchemaWrite).validate_python(
        {"name": attribute["name"], "kind": attribute["kind"], "parameters": {}}
    )
    return type(model), None if model.parameters is None else type(model.parameters)


def _values_missing_from_export(stored_element: NodeSchema | GenericSchema, exported: dict[str, Any]) -> dict[str, Any]:
    """Return each value of a stored element that the exported element does not hold, keyed by its path.

    The fields that the export leaves out on purpose and the deprecated fields that a schema file holds in
    another place are not checked.
    """
    is_node = isinstance(stored_element, NodeSchema)
    write_model = NodeSchemaWrite if is_node else GenericSchemaWrite
    stored = stored_element.model_dump()
    missing = _missing_values(exported, _valued_fields(write_model, stored, skipped=NOT_EXPORTED_FIELDS))

    exported_attributes = {attribute["name"]: attribute for attribute in exported.get("attributes", [])}
    for attribute in stored["attributes"]:
        if is_node and attribute["inherited"]:
            continue
        exported_attribute = exported_attributes.get(attribute["name"], {})
        attribute_model, parameters_model = _attribute_models(attribute)
        expected = _valued_fields(attribute_model, attribute, skipped=NOT_EXPORTED_FIELDS | DEPRECATED_ATTRIBUTE_FIELDS)
        missing.update(
            {
                f"attributes.{attribute['name']}.{name}": value
                for name, value in _missing_values(exported_attribute, expected).items()
            }
        )
        expected_parameters = (
            {}
            if parameters_model is None
            else _valued_fields(
                parameters_model, attribute.get("parameters") or {}, skipped=DEPRECATED_PARAMETER_FIELDS
            )
        )
        missing.update(
            {
                f"attributes.{attribute['name']}.parameters.{name}": value
                for name, value in _missing_values(
                    exported_attribute.get("parameters", {}), expected_parameters
                ).items()
            }
        )

    exported_relationships = {relationship["name"]: relationship for relationship in exported.get("relationships", [])}
    for relationship in stored["relationships"]:
        if (is_node and relationship["inherited"]) or relationship["kind"] in GENERATED_RELATIONSHIP_KINDS:
            continue
        expected = _valued_fields(RelationshipSchemaWrite, relationship, skipped=NOT_EXPORTED_FIELDS)
        missing.update(
            {
                f"relationships.{relationship['name']}.{name}": value
                for name, value in _missing_values(
                    exported_relationships.get(relationship["name"], {}), expected
                ).items()
            }
        )
    return missing


def _exported_elements(exported: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f"{element['namespace']}{element['name']}": element for element in exported["nodes"] + exported["generics"]}


def _full_export(schema_exporter: SchemaExporter, schema_branch: SchemaBranch) -> dict[str, dict[str, Any]]:
    document = schema_exporter.export(schema_branch=schema_branch, mode=SchemaExportMode.FULL, namespaces=None)
    return _exported_elements(document.model_dump(exclude_unset=True))


def test_full_export_loads_to_the_same_schema(variation_schema: VariationSchema, schema_round_trip: RoundTrip) -> None:
    schema_round_trip(variation_schema.payload(), SchemaExportMode.FULL)


def test_full_export_holds_every_value_of_the_stored_elements(
    variation_schema: VariationSchema, schema_exporter: SchemaExporter
) -> None:
    source = load_on_new_baseline(variation_schema.payload())
    elements = _full_export(schema_exporter, source)

    missing: dict[str, dict[str, Any]] = {}
    for kind, element in elements.items():
        stored = source.get(name=kind, duplicate=False)
        assert isinstance(stored, NodeSchema | GenericSchema)
        missing[kind] = _values_missing_from_export(stored, element)

    assert set(elements) == {
        f"{element['namespace']}{element['name']}"
        for element in variation_schema.schema.get("nodes", []) + variation_schema.schema.get("generics", [])
    }
    assert {kind: values for kind, values in missing.items() if values} == {}


def test_full_export_writes_the_state_of_each_element(
    variation_schema: VariationSchema, schema_exporter: SchemaExporter
) -> None:
    elements = _full_export(schema_exporter, load_on_new_baseline(variation_schema.payload()))

    states: dict[tuple[str, str | None, str | None], Any] = {
        (kind, None, None): element["state"] for kind, element in elements.items()
    }
    states.update(
        {
            (kind, collection, item["name"]): item["state"]
            for kind, element in elements.items()
            for collection in ("attributes", "relationships")
            for item in element[collection]
        }
    )
    assert len(states) > len(elements)
    assert set(states.values()) == {PRESENT_STATE}


def test_full_export_never_builds_a_baseline() -> None:
    built_baselines: list[str] = []

    def build_baseline(branch_name: str) -> SchemaBranch:
        built_baselines.append(branch_name)
        return build_core_schema_baseline(branch_name)

    exporter = SchemaExporter(baseline_factory=build_baseline)
    source = load_on_new_baseline(_device_schema(device_label="Network device", name_label="Hostname"))

    full_elements = _full_export(exporter, source)
    assert built_baselines == []

    exporter.export(schema_branch=source, mode=SchemaExportMode.BRIEF, namespaces=None)
    assert set(full_elements) == {"TestingDevice"}
    assert built_baselines == [ROUND_TRIP_BRANCH_NAME, ROUND_TRIP_BRANCH_NAME]


def test_full_export_writes_validation_settings_only_under_parameters(schema_exporter: SchemaExporter) -> None:
    source = load_on_new_baseline(DEPRECATED_VALIDATION_FIELDS.payload())
    attributes = {
        attribute["name"]: attribute for attribute in _full_export(schema_exporter, source)["LegacyHost"]["attributes"]
    }

    assert {name: attribute.get("parameters") for name, attribute in attributes.items()} == {
        "hostname": {"regex": "^[a-z0-9-]+$", "min_length": 3, "max_length": 32},
        "notes": {"regex": "^[^<>]*$", "min_length": 1, "max_length": 500},
        "aliases": {"regex": "^[a-z0-9-]+$"},
    }
    assert {name: DEPRECATED_ATTRIBUTE_FIELDS & attribute.keys() for name, attribute in attributes.items()} == {
        "hostname": set(),
        "notes": set(),
        # The parameters of a List attribute have no length settings, so those stay at the top level.
        "aliases": {"min_length", "max_length"},
    }


def test_full_export_writes_number_pool_bounds_only_as_ranges(schema_exporter: SchemaExporter) -> None:
    source = load_on_new_baseline(NUMBER_POOL_RANGES.payload())
    attributes = _full_export(schema_exporter, source)["PoolCircuit"]["attributes"]

    assert {
        attribute["name"]: attribute["parameters"] for attribute in attributes if attribute["kind"] == "NumberPool"
    } == {
        "vlan_id": {"ranges": [{"start": 100, "end": 200}]},
        "vni": {"ranges": [{"start": 5000}]},
        "circuit_index": {
            "ranges": [{"start": 1, "end": 50, "weight": 10}, {"start": 51, "end": 100}],
            "allocation_scope": ["site"],
        },
    }


def _device_schema(device_label: str, name_label: str) -> LabelledSchema:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Device",
                "namespace": "Testing",
                "label": device_label,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True, "label": name_label},
                    {"name": "serial_number", "kind": "Text", "optional": True},
                ],
            }
        ],
    }


@pytest.fixture
def labelled_sources() -> tuple[SchemaBranch, SchemaBranch]:
    """Two schemas with the same node and different labels, as on two instances."""
    first = load_on_new_baseline(_device_schema(device_label="Network device", name_label="Hostname"))
    second = load_on_new_baseline(_device_schema(device_label="Device", name_label="Name"))
    return first, second


def test_full_export_holds_the_labels_of_its_own_schema(
    schema_exporter: SchemaExporter, labelled_sources: tuple[SchemaBranch, SchemaBranch]
) -> None:
    first, second = labelled_sources

    first_device = _full_export(schema_exporter, first)["TestingDevice"]
    second_device = _full_export(schema_exporter, second)["TestingDevice"]

    assert (first_device["label"], second_device["label"]) == ("Network device", "Device")
    assert {attribute["name"]: attribute["label"] for attribute in first_device["attributes"]} == {
        "name": "Hostname",
        "serial_number": "Serial Number",
    }
    assert {attribute["name"]: attribute["label"] for attribute in second_device["attributes"]} == {
        "name": "Name",
        "serial_number": "Serial Number",
    }


def test_brief_export_leaves_out_the_label_derived_from_the_attribute_name(
    schema_exporter: SchemaExporter, labelled_sources: tuple[SchemaBranch, SchemaBranch]
) -> None:
    first, _ = labelled_sources

    document = schema_exporter.export(schema_branch=first, mode=SchemaExportMode.BRIEF, namespaces=None)
    device = _exported_elements(document.model_dump(exclude_unset=True))["TestingDevice"]

    assert device["label"] == "Network device"
    assert {attribute["name"]: attribute.get("label") for attribute in device["attributes"]} == {
        "name": "Hostname",
        "serial_number": None,
    }


def test_full_export_writes_the_derived_values(
    schema_exporter: SchemaExporter, labelled_sources: tuple[SchemaBranch, SchemaBranch]
) -> None:
    first, _ = labelled_sources

    device = _full_export(schema_exporter, first)["TestingDevice"]

    assert {name: device[name] for name in ("label", "branch", "human_friendly_id")} == {
        "label": "Network device",
        "branch": "aware",
        "human_friendly_id": ["name__value"],
    }
    assert [
        (attribute["name"], attribute["label"], attribute["branch"], attribute["order_weight"])
        for attribute in device["attributes"]
    ] == [("name", "Hostname", "aware", 1000), ("serial_number", "Serial Number", "aware", 2000)]


def test_full_export_of_one_namespace_holds_its_entries_as_in_the_unfiltered_export(
    export_with_and_without_filter: NamespaceFilterExports,
) -> None:
    filtered, unfiltered = export_with_and_without_filter(SchemaExportMode.FULL, [SELECTED_NAMESPACE])

    assert _exported_elements(unfiltered).keys() == {"NetworkDevice", "NetworkEndpoint", "LocationSite"}
    assert _exported_elements(filtered).keys() == {"NetworkDevice", "NetworkEndpoint"}
    assert {name: filtered[name] for name in ("nodes", "generics")} == elements_in_namespace(
        unfiltered, SELECTED_NAMESPACE
    )
    assert [
        relationship["peer"] for relationship in _exported_elements(filtered)["NetworkDevice"]["relationships"]
    ] == [f"{OTHER_NAMESPACE}Site"]


def test_full_export_ignores_a_restricted_namespace_in_the_filter(
    export_with_and_without_filter: NamespaceFilterExports,
) -> None:
    with_restricted, _ = export_with_and_without_filter(SchemaExportMode.FULL, [SELECTED_NAMESPACE, "Core"])
    without_restricted, _ = export_with_and_without_filter(SchemaExportMode.FULL, [SELECTED_NAMESPACE])
    only_restricted, _ = export_with_and_without_filter(SchemaExportMode.FULL, ["Core"])

    assert with_restricted == without_restricted
    assert (only_restricted["nodes"], only_restricted["generics"]) == ([], [])
