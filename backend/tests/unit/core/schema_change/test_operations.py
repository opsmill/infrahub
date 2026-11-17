from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from infrahub.core.schema_change.enums import SchemaOperationNodeType, SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operations import (
    SchemaOperation,
    build_schema_change_name,
    build_schema_change_summary,
)


@dataclass
class RefusedOperationCase:
    name: str
    fields: dict[str, Any]
    error: str


REFUSED_OPERATION_CASES: list[RefusedOperationCase] = [
    RefusedOperationCase(
        name="element_add_without_section",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_ADD,
            "kind": "DcimGenericDevice",
            "element_name": "serial",
            "value": {"name": "serial", "kind": "Text"},
        },
        error=r"Value error, Operation element_add requires 'section' and 'element_name' \[",
    ),
    RefusedOperationCase(
        name="element_remove_without_element_name",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_REMOVE,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
        },
        error=r"Value error, Operation element_remove requires 'section' and 'element_name' \[",
    ),
    RefusedOperationCase(
        name="element_property_without_section",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_PROPERTY,
            "kind": "DcimGenericDevice",
            "element_name": "serial",
            "property_name": "label",
            "value": "Serial number",
            "previous_value": "Serial",
        },
        error=r"Value error, Operation element_property requires 'section' and 'element_name' \[",
    ),
    RefusedOperationCase(
        name="element_property_without_property_name",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_PROPERTY,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "serial",
            "value": "Serial number",
            "previous_value": "Serial",
        },
        error=r"Value error, Operation element_property requires 'property_name' \[",
    ),
    RefusedOperationCase(
        name="node_property_without_property_name",
        fields={
            "operation_type": SchemaOperationType.NODE_PROPERTY,
            "kind": "DcimGenericDevice",
            "value": "Device",
            "previous_value": "Generic device",
        },
        error=r"Value error, Operation node_property requires 'property_name' \[",
    ),
    RefusedOperationCase(
        name="node_add_without_node_type",
        fields={
            "operation_type": SchemaOperationType.NODE_ADD,
            "kind": "DcimCloudDevice",
            "value": {"name": "CloudDevice", "namespace": "Dcim"},
        },
        error=r"Value error, Operation node_add requires 'node_type' \[",
    ),
    RefusedOperationCase(
        name="node_add_value_with_id",
        fields={
            "operation_type": SchemaOperationType.NODE_ADD,
            "kind": "DcimCloudDevice",
            "node_type": SchemaOperationNodeType.NODE,
            "value": {"id": "17a8f4c0-0000-0000-0000-000000000000", "name": "CloudDevice", "namespace": "Dcim"},
        },
        error=r"Value error, The value of operation node_add must not hold 'id' \[",
    ),
    RefusedOperationCase(
        name="node_add_attribute_with_id",
        fields={
            "operation_type": SchemaOperationType.NODE_ADD,
            "kind": "DcimCloudDevice",
            "node_type": SchemaOperationNodeType.NODE,
            "value": {
                "name": "CloudDevice",
                "namespace": "Dcim",
                "attributes": [{"id": "17a8f4c0-0000-0000-0000-000000000001", "name": "serial", "kind": "Text"}],
            },
        },
        error=r"Value error, The value of operation node_add must not hold 'id' in attributes 'serial' \[",
    ),
    RefusedOperationCase(
        name="node_add_relationship_with_id",
        fields={
            "operation_type": SchemaOperationType.NODE_ADD,
            "kind": "DcimCloudDevice",
            "node_type": SchemaOperationNodeType.NODE,
            "value": {
                "name": "CloudDevice",
                "namespace": "Dcim",
                "relationships": [
                    {"id": "17a8f4c0-0000-0000-0000-000000000002", "name": "site", "peer": "LocationSite"}
                ],
            },
        },
        error=r"Value error, The value of operation node_add must not hold 'id' in relationships 'site' \[",
    ),
    RefusedOperationCase(
        name="node_add_attribute_with_number_pool_id",
        fields={
            "operation_type": SchemaOperationType.NODE_ADD,
            "kind": "DcimCloudDevice",
            "node_type": SchemaOperationNodeType.NODE,
            "value": {
                "name": "CloudDevice",
                "namespace": "Dcim",
                "attributes": [
                    {
                        "name": "asset_number",
                        "kind": "NumberPool",
                        "parameters": {"number_pool_id": "17a8f4c0-0000-0000-0000-000000000003"},
                    }
                ],
            },
        },
        error=r"Value error, The value of operation node_add must not hold 'parameters.number_pool_id' in attributes 'asset_number' \[",
    ),
    RefusedOperationCase(
        name="element_add_value_with_id",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_ADD,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "serial",
            "value": {"id": "17a8f4c0-0000-0000-0000-000000000004", "name": "serial", "kind": "Text"},
        },
        error=r"Value error, The value of operation element_add must not hold 'id' \[",
    ),
    RefusedOperationCase(
        name="element_add_value_with_id_set_to_null",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_ADD,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "serial",
            "value": {"id": None, "name": "serial", "kind": "Text"},
        },
        error=r"Value error, The value of operation element_add must not hold 'id' \[",
    ),
    RefusedOperationCase(
        name="element_add_value_with_number_pool_id",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_ADD,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "asset_number",
            "value": {
                "name": "asset_number",
                "kind": "NumberPool",
                "parameters": {"number_pool_id": "17a8f4c0-0000-0000-0000-000000000005", "start_range": 1},
            },
        },
        error=r"Value error, The value of operation element_add must not hold 'parameters.number_pool_id' \[",
    ),
    RefusedOperationCase(
        name="element_add_value_not_a_definition",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_ADD,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "serial",
            "value": "serial",
        },
        error=r"Value error, Operation element_add requires a definition as its value \[",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSED_OPERATION_CASES])
def test_operation_is_refused(case: RefusedOperationCase) -> None:
    with pytest.raises(ValidationError, match=case.error):
        SchemaOperation(**case.fields)


@dataclass
class AcceptedOperationCase:
    name: str
    fields: dict[str, Any]


ACCEPTED_OPERATION_CASES: list[AcceptedOperationCase] = [
    AcceptedOperationCase(
        name="node_add_with_node_type",
        fields={
            "operation_type": SchemaOperationType.NODE_ADD,
            "kind": "DcimGenericDevice",
            "node_type": SchemaOperationNodeType.GENERIC,
            "value": {
                "name": "GenericDevice",
                "namespace": "Dcim",
                "attributes": [{"name": "asset_number", "kind": "NumberPool", "parameters": {"start_range": 1}}],
                "relationships": [{"name": "site", "peer": "LocationSite"}],
            },
        },
    ),
    AcceptedOperationCase(
        name="node_remove_with_kind_only",
        fields={"operation_type": SchemaOperationType.NODE_REMOVE, "kind": "DcimGenericDevice"},
    ),
    AcceptedOperationCase(
        name="element_remove_with_section_and_element_name",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_REMOVE,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.RELATIONSHIPS,
            "element_name": "site",
        },
    ),
    AcceptedOperationCase(
        name="element_property_with_nested_property_name",
        fields={
            "operation_type": SchemaOperationType.ELEMENT_PROPERTY,
            "kind": "DcimGenericDevice",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "serial",
            "property_name": "parameters.regex",
            "value": "^[A-Z]+$",
            "previous_value": None,
        },
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ACCEPTED_OPERATION_CASES])
def test_operation_is_accepted(case: AcceptedOperationCase) -> None:
    operation = SchemaOperation(**case.fields)

    assert operation.kind == case.fields["kind"]


def test_null_value_is_kept_apart_from_a_value_that_is_not_set() -> None:
    operation = SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_PROPERTY,
        kind="DcimGenericDevice",
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="serial",
        property_name="description",
        value=None,
    )

    reloaded = SchemaOperation.model_validate_json(operation.model_dump_json(exclude_unset=True))

    assert (reloaded.has_value, reloaded.has_previous_value) == (True, False)
    assert reloaded.value is None


@dataclass
class SummaryCase:
    name: str
    operations: list[SchemaOperation]
    expected: str


SERIAL_ADD = SchemaOperation(
    operation_type=SchemaOperationType.ELEMENT_ADD,
    kind="DcimGenericDevice",
    section=SchemaOperationSection.ATTRIBUTES,
    element_name="serial",
    value={"name": "serial", "kind": "Text"},
)
SITE_REMOVE = SchemaOperation(
    operation_type=SchemaOperationType.ELEMENT_REMOVE,
    kind="DcimGenericDevice",
    section=SchemaOperationSection.RELATIONSHIPS,
    element_name="site",
)

SUMMARY_CASES: list[SummaryCase] = [
    SummaryCase(name="element_add", operations=[SERIAL_ADD], expected="dcimgenericdevice_serial_add"),
    SummaryCase(name="element_remove", operations=[SITE_REMOVE], expected="dcimgenericdevice_site_remove"),
    SummaryCase(
        name="element_property_names_the_element",
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                kind="DcimGenericDevice",
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="serial",
                property_name="label",
                value="Serial number",
                previous_value="Serial",
            )
        ],
        expected="dcimgenericdevice_serial_update",
    ),
    SummaryCase(
        name="node_property_names_the_property",
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.NODE_PROPERTY,
                kind="DcimGenericDevice",
                property_name="generate_profile",
                value=True,
                previous_value=False,
            )
        ],
        expected="dcimgenericdevice_generate_profile_update",
    ),
    SummaryCase(
        name="node_add",
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.NODE_ADD,
                kind="DcimCloudDevice",
                node_type=SchemaOperationNodeType.NODE,
                value={"name": "CloudDevice", "namespace": "Dcim"},
            )
        ],
        expected="dcimclouddevice_add",
    ),
    SummaryCase(
        name="node_remove",
        operations=[SchemaOperation(operation_type=SchemaOperationType.NODE_REMOVE, kind="DcimCloudDevice")],
        expected="dcimclouddevice_remove",
    ),
    SummaryCase(
        name="two_operations",
        operations=[SERIAL_ADD, SITE_REMOVE],
        expected="dcimgenericdevice_serial_add_and_1_more",
    ),
    SummaryCase(
        name="three_operations",
        operations=[SERIAL_ADD, SITE_REMOVE, SITE_REMOVE],
        expected="dcimgenericdevice_serial_add_and_2_more",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SUMMARY_CASES])
def test_summary(case: SummaryCase) -> None:
    assert build_schema_change_summary(operations=case.operations) == case.expected


def test_summary_of_no_operation_is_refused() -> None:
    with pytest.raises(ValueError, match=r"at least one operation"):
        build_schema_change_summary(operations=[])


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param(8, "00008_dcimgenericdevice_serial_add", id="version_padded_to_five_digits"),
        pytest.param(99999, "99999_dcimgenericdevice_serial_add", id="largest_five_digit_version"),
        pytest.param(100000, "100000_dcimgenericdevice_serial_add", id="version_above_five_digits"),
        pytest.param(None, "dcimgenericdevice_serial_add", id="no_version_gives_the_summary"),
    ],
)
def test_name(version: int | None, expected: str) -> None:
    assert build_schema_change_name(version=version, summary="dcimgenericdevice_serial_add") == expected
