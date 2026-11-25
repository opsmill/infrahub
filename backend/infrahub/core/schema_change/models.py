from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.constants import SchemaPathType
    from infrahub.core.schema_change.enums import (
        SchemaChangeApplicationStatus,
        SchemaChangeMigrationStatus,
        SchemaChangeStatus,
        SchemaOperationNodeType,
        SchemaOperationSection,
        SchemaOperationType,
    )


@dataclass(frozen=True)
class SchemaChange:
    """One change to the schema of a branch, made of one or more operations."""

    uuid: str
    branch: str
    status: SchemaChangeStatus
    summary: str
    format_version: int
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    version: int | None = None
    """Set when the status becomes applied; unique among the applied schema changes of the branch."""

    applied_at: str | None = None
    """The timestamp of the graph writes of the application that applied it."""


@dataclass(frozen=True)
class SchemaChangeOperation:
    """One stored operation of a schema change; the operations apply in the order of `position`."""

    uuid: str
    position: int
    operation_type: SchemaOperationType
    kind: str
    created_at: str
    created_by: str
    node_type: SchemaOperationNodeType | None = None
    section: SchemaOperationSection | None = None
    element_name: str | None = None
    property_name: str | None = None
    value: str | None = None
    """JSON text, or `None` when the operation sets no value, so that the JSON value `null` is apart from no value."""

    previous_value: str | None = None
    """JSON text, or `None` when the operation has no previous value, so that the JSON value `null` is apart from none."""


@dataclass(frozen=True)
class SchemaChangeApplication:
    """One time a schema change was applied to a branch."""

    uuid: str
    branch: str
    status: SchemaChangeApplicationStatus
    at: str
    """The timestamp of every graph write of this application."""

    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    error: str | None = None


@dataclass(frozen=True)
class SchemaChangeMigration:
    """One migration that an application ran, identified inside its application by `position`."""

    uuid: str
    position: int
    migration_name: str
    path_type: SchemaPathType
    schema_kind: str
    status: SchemaChangeMigrationStatus
    created_at: str
    updated_at: str
    field_name: str | None = None
    property_name: str | None = None
    nbr_migrations_executed: int | None = None
    errors: tuple[str, ...] = ()
