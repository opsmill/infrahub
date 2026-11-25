from __future__ import annotations

import json
from typing import TYPE_CHECKING

from infrahub.core.constants import SchemaPathType
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import JsonValue

    from infrahub.core.query import CypherValue

type RecordProperty = str | int | list[str]
type RecordProperties = dict[str, RecordProperty]


class SchemaChangeRecordSerializer:
    """Turn a schema change record into the properties a query writes, and the properties a query returns into a record.

    A field that is `None` is a property that is not set, so a text property can hold any text.
    `value` and `previous_value` of an operation are JSON text, so the JSON value `null` is apart
    from a value that is not set.
    """

    def schema_change_to_properties(self, record: SchemaChange) -> RecordProperties:
        return _without_unset(
            {
                "uuid": record.uuid,
                "branch": record.branch,
                "status": record.status.value,
                "version": record.version,
                "summary": record.summary,
                "format_version": record.format_version,
                "applied_at": record.applied_at,
                "created_at": record.created_at,
                "created_by": record.created_by,
                "updated_at": record.updated_at,
                "updated_by": record.updated_by,
            }
        )

    def schema_change_from_properties(self, properties: Mapping[str, CypherValue]) -> SchemaChange:
        """Build a schema change from the properties of its vertex.

        Raises:
            ValueError: When a property is missing or holds a value of another type.

        """
        reader = _PropertyReader(record=SchemaChange.__name__, properties=properties)
        return SchemaChange(
            uuid=reader.text("uuid"),
            branch=reader.text("branch"),
            status=SchemaChangeStatus(reader.text("status")),
            version=reader.optional_integer("version"),
            summary=reader.text("summary"),
            format_version=reader.integer("format_version"),
            applied_at=reader.optional_text("applied_at"),
            created_at=reader.text("created_at"),
            created_by=reader.text("created_by"),
            updated_at=reader.text("updated_at"),
            updated_by=reader.text("updated_by"),
        )

    def operation_to_properties(self, record: SchemaChangeOperation) -> RecordProperties:
        return _without_unset(
            {
                "uuid": record.uuid,
                "position": record.position,
                "operation_type": record.operation_type.value,
                "kind": record.kind,
                "node_type": record.node_type.value if record.node_type is not None else None,
                "section": record.section.value if record.section is not None else None,
                "element_name": record.element_name,
                "property_name": record.property_name,
                "value": record.value,
                "previous_value": record.previous_value,
                "created_at": record.created_at,
                "created_by": record.created_by,
            }
        )

    def operation_from_properties(self, properties: Mapping[str, CypherValue]) -> SchemaChangeOperation:
        """Build an operation record from the properties of its vertex.

        Raises:
            ValueError: When a property is missing or holds a value of another type.

        """
        reader = _PropertyReader(record=SchemaChangeOperation.__name__, properties=properties)
        node_type = reader.optional_text("node_type")
        section = reader.optional_text("section")
        return SchemaChangeOperation(
            uuid=reader.text("uuid"),
            position=reader.integer("position"),
            operation_type=SchemaOperationType(reader.text("operation_type")),
            kind=reader.text("kind"),
            node_type=SchemaOperationNodeType(node_type) if node_type is not None else None,
            section=SchemaOperationSection(section) if section is not None else None,
            element_name=reader.optional_text("element_name"),
            property_name=reader.optional_text("property_name"),
            value=reader.optional_text("value"),
            previous_value=reader.optional_text("previous_value"),
            created_at=reader.text("created_at"),
            created_by=reader.text("created_by"),
        )

    def operation_to_record(
        self, *, uuid: str, position: int, operation: SchemaOperation, created_at: str, created_by: str
    ) -> SchemaChangeOperation:
        return SchemaChangeOperation(
            uuid=uuid,
            position=position,
            operation_type=operation.operation_type,
            kind=operation.kind,
            node_type=operation.node_type,
            section=operation.section,
            element_name=operation.element_name,
            property_name=operation.property_name,
            value=json.dumps(operation.value) if operation.has_value else None,
            previous_value=json.dumps(operation.previous_value) if operation.has_previous_value else None,
            created_at=created_at,
            created_by=created_by,
        )

    def record_to_operation(self, record: SchemaChangeOperation) -> SchemaOperation:
        """Build the operation of a record, setting `value` and `previous_value` only when the record holds them."""
        fields: dict[str, JsonValue] = {"operation_type": record.operation_type.value, "kind": record.kind}
        if record.node_type is not None:
            fields["node_type"] = record.node_type.value
        if record.section is not None:
            fields["section"] = record.section.value
        if record.element_name is not None:
            fields["element_name"] = record.element_name
        if record.property_name is not None:
            fields["property_name"] = record.property_name
        if record.value is not None:
            fields["value"] = json.loads(record.value)
        if record.previous_value is not None:
            fields["previous_value"] = json.loads(record.previous_value)
        return SchemaOperation.model_validate(fields)

    def application_to_properties(self, record: SchemaChangeApplication) -> RecordProperties:
        return _without_unset(
            {
                "uuid": record.uuid,
                "branch": record.branch,
                "status": record.status.value,
                "at": record.at,
                "error": record.error,
                "created_at": record.created_at,
                "created_by": record.created_by,
                "updated_at": record.updated_at,
                "updated_by": record.updated_by,
            }
        )

    def application_from_properties(self, properties: Mapping[str, CypherValue]) -> SchemaChangeApplication:
        """Build an application from the properties of its vertex.

        Raises:
            ValueError: When a property is missing or holds a value of another type.

        """
        reader = _PropertyReader(record=SchemaChangeApplication.__name__, properties=properties)
        return SchemaChangeApplication(
            uuid=reader.text("uuid"),
            branch=reader.text("branch"),
            status=SchemaChangeApplicationStatus(reader.text("status")),
            at=reader.text("at"),
            error=reader.optional_text("error"),
            created_at=reader.text("created_at"),
            created_by=reader.text("created_by"),
            updated_at=reader.text("updated_at"),
            updated_by=reader.text("updated_by"),
        )

    def migration_to_properties(self, record: SchemaChangeMigration) -> RecordProperties:
        return _without_unset(
            {
                "uuid": record.uuid,
                "position": record.position,
                "migration_name": record.migration_name,
                "path_type": record.path_type.value,
                "schema_kind": record.schema_kind,
                "field_name": record.field_name,
                "property_name": record.property_name,
                "status": record.status.value,
                "nbr_migrations_executed": record.nbr_migrations_executed,
                "errors": list(record.errors),
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        )

    def migration_from_properties(self, properties: Mapping[str, CypherValue]) -> SchemaChangeMigration:
        """Build a migration record from the properties of its vertex.

        Raises:
            ValueError: When a property is missing or holds a value of another type.

        """
        reader = _PropertyReader(record=SchemaChangeMigration.__name__, properties=properties)
        return SchemaChangeMigration(
            uuid=reader.text("uuid"),
            position=reader.integer("position"),
            migration_name=reader.text("migration_name"),
            path_type=SchemaPathType(reader.text("path_type")),
            schema_kind=reader.text("schema_kind"),
            field_name=reader.optional_text("field_name"),
            property_name=reader.optional_text("property_name"),
            status=SchemaChangeMigrationStatus(reader.text("status")),
            nbr_migrations_executed=reader.optional_integer("nbr_migrations_executed"),
            errors=reader.texts("errors"),
            created_at=reader.text("created_at"),
            updated_at=reader.text("updated_at"),
        )


def _without_unset(properties: Mapping[str, RecordProperty | None]) -> RecordProperties:
    return {key: value for key, value in properties.items() if value is not None}


class _PropertyReader:
    def __init__(self, record: str, properties: Mapping[str, CypherValue]) -> None:
        self.record = record
        self.properties = properties

    def text(self, key: str) -> str:
        value = self.optional_text(key)
        if value is None:
            raise ValueError(f"The property {key} of a {self.record} is not set")
        return value

    def optional_text(self, key: str) -> str | None:
        value = self.properties.get(key)
        if value is None or isinstance(value, str):
            return value
        raise ValueError(f"The property {key} of a {self.record} is not a text")

    def integer(self, key: str) -> int:
        value = self.optional_integer(key)
        if value is None:
            raise ValueError(f"The property {key} of a {self.record} is not set")
        return value

    def optional_integer(self, key: str) -> int | None:
        value = self.properties.get(key)
        if value is None or (isinstance(value, int) and not isinstance(value, bool)):
            return value
        raise ValueError(f"The property {key} of a {self.record} is not an integer")

    def texts(self, key: str) -> tuple[str, ...]:
        value = self.properties.get(key)
        if not isinstance(value, list):
            raise ValueError(f"The property {key} of a {self.record} is not a list")
        texts: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"The property {key} of a {self.record} holds an item that is not a text")
            texts.append(item)
        return tuple(texts)
