from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import pytest
from infrahub_sdk.schema.generated.write import NodeSchemaWrite

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.exceptions import SchemaNamespaceNotFoundError
from infrahub.schema.export.exporter import (
    SchemaExporter,
    build_core_schema_baseline,
    convert_deprecated_attribute_fields,
    normalize_element_for_comparison,
)
from infrahub.schema.export.models import SchemaExportMode

from .conftest import SELECTED_NAMESPACE, TWO_NAMESPACE_SCHEMA, load_on_new_baseline


def _defined_kinds(element_type: str) -> set[str]:
    return {
        f"{element['namespace']}{element['name']}"
        for definitions in (internal_schema, core_models, deprecated_models)
        for element in definitions.get(element_type, [])
    }


def test_baseline_holds_the_processed_core_schema() -> None:
    baseline = build_core_schema_baseline("main")

    assert baseline.name == "main"
    assert set(baseline.nodes) == _defined_kinds("nodes")
    assert set(baseline.generics) == _defined_kinds("generics")
    assert "ProfileBuiltinTag" in baseline.profiles


def test_each_baseline_has_a_schema_cache_of_its_own() -> None:
    first = build_core_schema_baseline("main")
    second = build_core_schema_baseline("main")
    second_hash = second.get_hash()
    second_cache_size = len(second._cache)

    first.load_schema(
        schema=SchemaRoot(
            nodes=[
                {"name": "Widget", "namespace": "Testing", "attributes": [{"name": "name", "kind": "Text"}]},
            ]
        )
    )
    first.process()

    assert first is not second
    assert first._cache is not second._cache
    assert "TestingWidget" in first.nodes
    assert "TestingWidget" not in second.nodes
    assert second.get_hash() == second_hash
    assert len(second._cache) == second_cache_size


@dataclass
class ConvertAttributeTestCase:
    name: str
    attribute: dict[str, Any]
    expected: dict[str, Any]


CONVERT_ATTRIBUTE_TEST_CASES: list[ConvertAttributeTestCase] = [
    ConvertAttributeTestCase(
        name="text_top_level_fields_move_into_unset_parameters",
        attribute={
            "name": "description",
            "kind": "Text",
            "regex": "^a",
            "min_length": 1,
            "max_length": 5,
            "parameters": {"regex": None, "min_length": None, "max_length": None},
        },
        expected={
            "name": "description",
            "kind": "Text",
            "parameters": {"regex": "^a", "min_length": 1, "max_length": 5},
        },
    ),
    ConvertAttributeTestCase(
        name="text_area_top_level_fields_equal_to_parameters_are_dropped",
        attribute={
            "name": "description",
            "kind": "TextArea",
            "regex": "^a",
            "min_length": None,
            "max_length": 5,
            "parameters": {"regex": "^a", "min_length": None, "max_length": 5},
        },
        expected={
            "name": "description",
            "kind": "TextArea",
            "parameters": {"regex": "^a", "min_length": None, "max_length": 5},
        },
    ),
    ConvertAttributeTestCase(
        name="text_parameters_value_wins_over_top_level_value",
        attribute={"name": "description", "kind": "Text", "regex": "^a", "parameters": {"regex": "^b"}},
        expected={"name": "description", "kind": "Text", "parameters": {"regex": "^b"}},
    ),
    ConvertAttributeTestCase(
        name="text_without_parameters_gets_parameters",
        attribute={"name": "description", "kind": "Text", "max_length": 7},
        expected={"name": "description", "kind": "Text", "parameters": {"max_length": 7}},
    ),
    ConvertAttributeTestCase(
        name="list_moves_regex_and_keeps_lengths_its_parameters_do_not_support",
        attribute={"name": "tags", "kind": "List", "regex": "^a", "min_length": 2, "parameters": {}},
        expected={"name": "tags", "kind": "List", "min_length": 2, "parameters": {"regex": "^a"}},
    ),
    ConvertAttributeTestCase(
        name="number_attribute_is_unchanged",
        attribute={"name": "count", "kind": "Number", "regex": None, "parameters": {"min_value": 1}},
        expected={"name": "count", "kind": "Number", "regex": None, "parameters": {"min_value": 1}},
    ),
    ConvertAttributeTestCase(
        name="attribute_without_parameters_is_unchanged",
        attribute={"name": "enabled", "kind": "Boolean"},
        expected={"name": "enabled", "kind": "Boolean"},
    ),
    ConvertAttributeTestCase(
        name="number_pool_start_and_end_become_one_range",
        attribute={"name": "vlan", "kind": "NumberPool", "parameters": {"start_range": 10, "end_range": 20}},
        expected={"name": "vlan", "kind": "NumberPool", "parameters": {"ranges": [{"start": 10, "end": 20}]}},
    ),
    ConvertAttributeTestCase(
        name="number_pool_start_only_leaves_end_unset",
        attribute={"name": "vlan", "kind": "NumberPool", "parameters": {"start_range": 10}},
        expected={"name": "vlan", "kind": "NumberPool", "parameters": {"ranges": [{"start": 10}]}},
    ),
    ConvertAttributeTestCase(
        name="number_pool_end_only_leaves_start_unset",
        attribute={"name": "vlan", "kind": "NumberPool", "parameters": {"start_range": None, "end_range": 20}},
        expected={"name": "vlan", "kind": "NumberPool", "parameters": {"ranges": [{"end": 20}]}},
    ),
    ConvertAttributeTestCase(
        name="number_pool_unset_bounds_are_dropped_and_ranges_kept",
        attribute={
            "name": "vlan",
            "kind": "NumberPool",
            "parameters": {"start_range": None, "end_range": None, "ranges": [{"start": 1, "end": 5}]},
        },
        expected={"name": "vlan", "kind": "NumberPool", "parameters": {"ranges": [{"start": 1, "end": 5}]}},
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(test_case, id=test_case.name) for test_case in CONVERT_ATTRIBUTE_TEST_CASES],
)
def test_convert_deprecated_attribute_fields(test_case: ConvertAttributeTestCase) -> None:
    original = copy.deepcopy(test_case.attribute)

    assert convert_deprecated_attribute_fields(test_case.attribute) == test_case.expected
    assert test_case.attribute == original


def test_normalize_element_for_comparison_ignores_ids_and_deprecated_forms() -> None:
    with_ids = {
        "id": "node-id",
        "name": "Device",
        "namespace": "Testing",
        "attributes": [
            {"id": "attribute-id", "name": "vlan", "kind": "NumberPool", "parameters": {"start_range": 10}},
        ],
        "relationships": [{"id": "relationship-id", "name": "site", "peer": "TestingSite"}],
    }
    without_ids = {
        "name": "Device",
        "namespace": "Testing",
        "attributes": [{"name": "vlan", "kind": "NumberPool", "parameters": {"ranges": [{"start": 10}]}}],
        "relationships": [{"name": "site", "peer": "TestingSite"}],
    }
    original = copy.deepcopy(with_ids)

    normalized = normalize_element_for_comparison(with_ids, write_model=NodeSchemaWrite)

    assert normalized == normalize_element_for_comparison(without_ids, write_model=NodeSchemaWrite)
    assert "id" not in normalized
    assert ["id" in attribute for attribute in normalized["attributes"]] == [False]
    assert ["id" in relationship for relationship in normalized["relationships"]] == [False]
    assert normalized["attributes"][0]["parameters"]["ranges"] == [{"start": 10, "end": None, "weight": None}]
    assert with_ids == original


def _device_schema(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Device",
                "namespace": "Testing",
                "attributes": [{"name": "name", "kind": "Text", "unique": True}, *attributes],
            }
        ],
    }


def test_stored_deprecated_and_current_forms_compare_equal() -> None:
    deprecated_form = load_on_new_baseline(
        _device_schema(
            [
                {"name": "description", "kind": "Text", "regex": "^a", "max_length": 20, "optional": True},
                {
                    "name": "vlan",
                    "kind": "NumberPool",
                    "read_only": True,
                    "parameters": {"start_range": 10, "end_range": 20},
                },
            ]
        )
    )
    current_form = load_on_new_baseline(
        _device_schema(
            [
                {
                    "name": "description",
                    "kind": "Text",
                    "parameters": {"regex": "^a", "max_length": 20},
                    "optional": True,
                },
                {
                    "name": "vlan",
                    "kind": "NumberPool",
                    "read_only": True,
                    "parameters": {"ranges": [{"start": 10, "end": 20}]},
                },
            ]
        )
    )
    deprecated_dump = deprecated_form.get(name="TestingDevice", duplicate=False).model_dump()
    current_dump = current_form.get(name="TestingDevice", duplicate=False).model_dump()

    assert deprecated_dump != current_dump
    assert normalize_element_for_comparison(
        deprecated_dump, write_model=NodeSchemaWrite
    ) == normalize_element_for_comparison(current_dump, write_model=NodeSchemaWrite)


@pytest.mark.parametrize("mode", [SchemaExportMode.FULL, SchemaExportMode.BRIEF])
def test_export_writes_attributes_and_relationships_by_order_weight(
    schema_exporter: SchemaExporter, mode: SchemaExportMode
) -> None:
    source = load_on_new_baseline(
        {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Rack",
                    "namespace": "Ordered",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True, "order_weight": 3000},
                        {"name": "height", "kind": "Number", "optional": True, "order_weight": 1000},
                        {"name": "width", "kind": "Number", "optional": True, "order_weight": 1000},
                    ],
                    "relationships": [
                        {
                            "name": "row",
                            "peer": "OrderedRack",
                            "cardinality": "one",
                            "identifier": "rack__row",
                            "order_weight": 5000,
                        },
                        {
                            "name": "site",
                            "peer": "OrderedRack",
                            "cardinality": "one",
                            "identifier": "rack__site",
                            "order_weight": 4000,
                        },
                    ],
                }
            ],
        }
    )

    document = schema_exporter.export(schema_branch=source, mode=mode, namespaces=None)

    rack = document.nodes[0]
    assert [attribute.name for attribute in rack.attributes] == ["height", "width", "name"]
    assert [relationship.name for relationship in rack.relationships] == ["site", "row"]


@pytest.mark.parametrize("mode", [SchemaExportMode.BRIEF, SchemaExportMode.FULL])
def test_export_rejects_every_restricted_or_unknown_namespace_of_the_filter(
    schema_exporter: SchemaExporter, mode: SchemaExportMode
) -> None:
    source = load_on_new_baseline(TWO_NAMESPACE_SCHEMA)

    with pytest.raises(
        SchemaNamespaceNotFoundError,
        match=(
            r"^The namespace 'Core' is reserved for Infrahub and cannot be exported; "
            r"The namespace 'Netwrk' does not exist on the branch 'main'$"
        ),
    ) as error:
        schema_exporter.export(
            schema_branch=source, mode=mode, namespaces=[SELECTED_NAMESPACE, "Core", "Netwrk", "Core"]
        )

    assert error.value.errors == [
        "The namespace 'Core' is reserved for Infrahub and cannot be exported",
        "The namespace 'Netwrk' does not exist on the branch 'main'",
    ]
    assert error.value.error_extensions == [{"namespace": "Core"}, {"namespace": "Netwrk"}]


def test_export_of_a_namespace_that_holds_only_kinds_infrahub_defines_is_empty(
    schema_exporter: SchemaExporter,
) -> None:
    source = load_on_new_baseline(TWO_NAMESPACE_SCHEMA)

    document = schema_exporter.export(schema_branch=source, mode=SchemaExportMode.FULL, namespaces=["Ipam"])

    assert (document.nodes, document.generics) == ([], [])
