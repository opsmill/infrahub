from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeSource,
    SchemaChangeStatus,
    SchemaOperationNodeType,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.models import (
    SchemaChange,
    SchemaChangeApplication,
    SchemaChangeMigration,
    SchemaChangeOperation,
)
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.schema_change.record_serializer import SchemaChangeRecordSerializer

if TYPE_CHECKING:
    from infrahub.core.query import CypherValue

UUID = "18a2cd5c-3f0b-4c41-9d3e-6a1d7c2b9e10"
CREATED_AT = "2026-11-18T10:00:00.000000Z"
UPDATED_AT = "2026-11-18T10:05:00.000000Z"
USER_ID = "a1b2c3d4-0000-4000-8000-000000000001"

RUNNING_SCHEMA_CHANGE = SchemaChange(
    uuid=UUID,
    branch="main",
    status=SchemaChangeStatus.RUNNING,
    source=SchemaChangeSource.USER,
    summary="testcar_color_update",
    format_version=1,
    created_at=CREATED_AT,
    created_by=USER_ID,
    updated_at=UPDATED_AT,
    updated_by=USER_ID,
)
RUNNING_SCHEMA_CHANGE_PROPERTIES: dict[str, CypherValue] = {
    "uuid": UUID,
    "branch": "main",
    "status": "running",
    "source": "user",
    "summary": "testcar_color_update",
    "format_version": 1,
    "created_at": CREATED_AT,
    "created_by": USER_ID,
    "updated_at": UPDATED_AT,
    "updated_by": USER_ID,
}


def _element_property(**values: object) -> SchemaOperation:
    return SchemaOperation.model_validate(
        {
            "operation_type": SchemaOperationType.ELEMENT_PROPERTY,
            "kind": "TestCar",
            "section": SchemaOperationSection.ATTRIBUTES,
            "element_name": "color",
            "property_name": "label",
            **values,
        }
    )


def test_schema_change_without_version_has_no_version_and_no_applied_at_property() -> None:
    serializer = SchemaChangeRecordSerializer()

    assert serializer.schema_change_to_properties(record=RUNNING_SCHEMA_CHANGE) == RUNNING_SCHEMA_CHANGE_PROPERTIES
    assert (
        serializer.schema_change_from_properties(properties=RUNNING_SCHEMA_CHANGE_PROPERTIES) == RUNNING_SCHEMA_CHANGE
    )


def test_schema_change_without_source_property_reads_as_user() -> None:
    serializer = SchemaChangeRecordSerializer()
    properties = {key: value for key, value in RUNNING_SCHEMA_CHANGE_PROPERTIES.items() if key != "source"}

    assert serializer.schema_change_from_properties(properties=properties).source == SchemaChangeSource.USER


def test_core_schema_update_source_round_trips() -> None:
    serializer = SchemaChangeRecordSerializer()
    record = replace(RUNNING_SCHEMA_CHANGE, source=SchemaChangeSource.CORE_SCHEMA_UPDATE)
    properties: dict[str, CypherValue] = {**RUNNING_SCHEMA_CHANGE_PROPERTIES, "source": "core_schema_update"}

    assert serializer.schema_change_to_properties(record=record) == properties
    assert serializer.schema_change_from_properties(properties=properties) == record


def test_applied_schema_change_keeps_its_version_and_applied_at() -> None:
    serializer = SchemaChangeRecordSerializer()
    properties: dict[str, CypherValue] = {
        **RUNNING_SCHEMA_CHANGE_PROPERTIES,
        "status": "applied",
        "version": 3,
        "applied_at": UPDATED_AT,
    }

    record = serializer.schema_change_from_properties(properties=properties)

    assert record == SchemaChange(
        uuid=UUID,
        branch="main",
        status=SchemaChangeStatus.APPLIED,
        source=SchemaChangeSource.USER,
        summary="testcar_color_update",
        format_version=1,
        created_at=CREATED_AT,
        created_by=USER_ID,
        updated_at=UPDATED_AT,
        updated_by=USER_ID,
        version=3,
        applied_at=UPDATED_AT,
    )
    assert serializer.schema_change_to_properties(record=record) == properties


@dataclass(frozen=True)
class OperationValueCase:
    name: str
    operation: SchemaOperation
    expected_properties: dict[str, CypherValue]
    """The properties of the value and the previous value only."""


OPERATION_VALUE_CASES = [
    OperationValueCase(
        name="json_null_value_and_no_previous_value",
        operation=_element_property(value=None),
        expected_properties={"value": "null"},
    ),
    OperationValueCase(
        name="no_value_and_json_null_previous_value",
        operation=_element_property(previous_value=None),
        expected_properties={"previous_value": "null"},
    ),
    OperationValueCase(name="neither_value_is_set", operation=_element_property(), expected_properties={}),
    OperationValueCase(
        name="the_text_null_is_a_json_text",
        operation=_element_property(value="NULL", previous_value="Color"),
        expected_properties={"value": '"NULL"', "previous_value": '"Color"'},
    ),
    OperationValueCase(
        name="list_and_object_values",
        operation=_element_property(value=["red", "blue"], previous_value={"regex": "^[a-z]+$"}),
        expected_properties={"value": '["red", "blue"]', "previous_value": '{"regex": "^[a-z]+$"}'},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OPERATION_VALUE_CASES])
def test_operation_value_is_json_text_and_a_value_not_set_is_a_missing_property(test_case: OperationValueCase) -> None:
    serializer = SchemaChangeRecordSerializer()
    record = serializer.operation_to_record(
        uuid=UUID, position=2, operation=test_case.operation, created_at=CREATED_AT, created_by=USER_ID
    )

    expected: dict[str, CypherValue] = {
        "uuid": UUID,
        "position": 2,
        "operation_type": "element_property",
        "kind": "TestCar",
        "section": "attributes",
        "element_name": "color",
        "property_name": "label",
        "created_at": CREATED_AT,
        "created_by": USER_ID,
        **test_case.expected_properties,
    }
    assert serializer.operation_to_properties(record=record) == expected
    read_back = serializer.operation_from_properties(properties=expected)
    assert read_back == record
    operation = serializer.record_to_operation(record=read_back)
    assert operation == test_case.operation
    assert (operation.has_value, operation.has_previous_value) == (
        test_case.operation.has_value,
        test_case.operation.has_previous_value,
    )


def test_node_add_operation_keeps_its_node_type_and_has_no_section_property() -> None:
    serializer = SchemaChangeRecordSerializer()
    operation = SchemaOperation(
        operation_type=SchemaOperationType.NODE_ADD,
        kind="TestBoat",
        node_type=SchemaOperationNodeType.GENERIC,
        value={"name": "Boat", "namespace": "Test"},
    )
    record = serializer.operation_to_record(
        uuid=UUID, position=0, operation=operation, created_at=CREATED_AT, created_by=USER_ID
    )

    expected: dict[str, CypherValue] = {
        "uuid": UUID,
        "position": 0,
        "operation_type": "node_add",
        "kind": "TestBoat",
        "node_type": "generic",
        "value": '{"name": "Boat", "namespace": "Test"}',
        "created_at": CREATED_AT,
        "created_by": USER_ID,
    }
    assert serializer.operation_to_properties(record=record) == expected
    assert serializer.record_to_operation(record=serializer.operation_from_properties(properties=expected)) == operation


@dataclass(frozen=True)
class ApplicationCase:
    name: str
    record: SchemaChangeApplication
    properties: dict[str, CypherValue]


APPLICATION_PROPERTIES: dict[str, CypherValue] = {
    "uuid": UUID,
    "branch": "branch1",
    "at": CREATED_AT,
    "created_at": CREATED_AT,
    "created_by": USER_ID,
    "updated_at": UPDATED_AT,
    "updated_by": USER_ID,
}

APPLICATION_CASES = [
    ApplicationCase(
        name="without_error",
        record=SchemaChangeApplication(
            uuid=UUID,
            branch="branch1",
            status=SchemaChangeApplicationStatus.APPLIED,
            at=CREATED_AT,
            created_at=CREATED_AT,
            created_by=USER_ID,
            updated_at=UPDATED_AT,
            updated_by=USER_ID,
        ),
        properties={**APPLICATION_PROPERTIES, "status": "applied"},
    ),
    ApplicationCase(
        name="with_the_text_null_as_error",
        record=SchemaChangeApplication(
            uuid=UUID,
            branch="branch1",
            status=SchemaChangeApplicationStatus.FAILED,
            at=CREATED_AT,
            created_at=CREATED_AT,
            created_by=USER_ID,
            updated_at=UPDATED_AT,
            updated_by=USER_ID,
            error="NULL",
        ),
        properties={**APPLICATION_PROPERTIES, "status": "failed", "error": "NULL"},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in APPLICATION_CASES])
def test_application_round_trips_through_its_properties(test_case: ApplicationCase) -> None:
    serializer = SchemaChangeRecordSerializer()

    assert serializer.application_to_properties(record=test_case.record) == test_case.properties
    assert serializer.application_from_properties(properties=test_case.properties) == test_case.record


def test_waiting_migration_has_no_count_and_no_property_name_property() -> None:
    serializer = SchemaChangeRecordSerializer()
    record = SchemaChangeMigration(
        uuid=UUID,
        position=1,
        migration_name="node.attribute.add",
        path_type=SchemaPathType.ATTRIBUTE,
        schema_kind="TestCar",
        field_name="color",
        status=SchemaChangeMigrationStatus.WAITING,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    expected: dict[str, CypherValue] = {
        "uuid": UUID,
        "position": 1,
        "migration_name": "node.attribute.add",
        "path_type": "attribute",
        "schema_kind": "TestCar",
        "field_name": "color",
        "status": "waiting",
        "errors": [],
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    assert serializer.migration_to_properties(record=record) == expected
    assert serializer.migration_from_properties(properties=expected) == record


def test_failed_migration_keeps_its_count_of_zero_and_its_errors() -> None:
    serializer = SchemaChangeRecordSerializer()
    properties: dict[str, CypherValue] = {
        "uuid": UUID,
        "position": 0,
        "migration_name": "attribute.kind.update",
        "path_type": "attribute",
        "schema_kind": "TestCar",
        "field_name": "name",
        "status": "failed",
        "nbr_migrations_executed": 0,
        "errors": ["first error", "second error"],
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
    }

    record = serializer.migration_from_properties(properties=properties)

    assert record == SchemaChangeMigration(
        uuid=UUID,
        position=0,
        migration_name="attribute.kind.update",
        path_type=SchemaPathType.ATTRIBUTE,
        schema_kind="TestCar",
        field_name="name",
        status=SchemaChangeMigrationStatus.FAILED,
        nbr_migrations_executed=0,
        errors=("first error", "second error"),
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )
    assert serializer.migration_to_properties(record=record) == properties


@dataclass(frozen=True)
class InvalidPropertiesCase:
    name: str
    properties: dict[str, CypherValue]
    error: str


INVALID_SCHEMA_CHANGE_CASES = [
    InvalidPropertiesCase(
        name="missing_required_text",
        properties={key: value for key, value in RUNNING_SCHEMA_CHANGE_PROPERTIES.items() if key != "branch"},
        error=r"^The property branch of a SchemaChange is not set$",
    ),
    InvalidPropertiesCase(
        name="missing_required_integer",
        properties={key: value for key, value in RUNNING_SCHEMA_CHANGE_PROPERTIES.items() if key != "format_version"},
        error=r"^The property format_version of a SchemaChange is not set$",
    ),
    InvalidPropertiesCase(
        name="text_that_is_an_integer",
        properties={**RUNNING_SCHEMA_CHANGE_PROPERTIES, "summary": 3},
        error=r"^The property summary of a SchemaChange is not a text$",
    ),
    InvalidPropertiesCase(
        name="integer_that_is_a_boolean",
        properties={**RUNNING_SCHEMA_CHANGE_PROPERTIES, "version": True},
        error=r"^The property version of a SchemaChange is not an integer$",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in INVALID_SCHEMA_CHANGE_CASES])
def test_schema_change_from_invalid_properties_raises(test_case: InvalidPropertiesCase) -> None:
    with pytest.raises(ValueError, match=test_case.error):
        SchemaChangeRecordSerializer().schema_change_from_properties(properties=test_case.properties)


def test_migration_whose_errors_hold_an_item_that_is_not_a_text_raises() -> None:
    properties: dict[str, CypherValue] = {
        "uuid": UUID,
        "position": 0,
        "migration_name": "node.attribute.add",
        "path_type": "attribute",
        "schema_kind": "TestCar",
        "status": "failed",
        "errors": ["first error", 2],
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
    }

    with pytest.raises(
        ValueError, match=r"^The property errors of a SchemaChangeMigration holds an item that is not a text$"
    ):
        SchemaChangeRecordSerializer().migration_from_properties(properties=properties)


def test_operation_record_of_a_stored_operation_keeps_the_record_fields() -> None:
    record = SchemaChangeOperation(
        uuid=UUID,
        position=4,
        operation_type=SchemaOperationType.ELEMENT_REMOVE,
        kind="TestCar",
        section=SchemaOperationSection.RELATIONSHIPS,
        element_name="owner",
        created_at=CREATED_AT,
        created_by=USER_ID,
    )

    assert SchemaChangeRecordSerializer().record_to_operation(record=record) == SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_REMOVE,
        kind="TestCar",
        section=SchemaOperationSection.RELATIONSHIPS,
        element_name="owner",
    )
