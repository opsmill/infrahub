from pydantic import Field

from infrahub.core.constants import SchemaPathType
from infrahub.core.node.standard import StandardNode
from infrahub.core.schema_change.constants import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
    SchemaOperationNodeType,
    SchemaOperationSection,
    SchemaOperationType,
)


class SchemaChange(StandardNode):
    """One change to the schema of a branch, made of one or more operations."""

    branch: str
    status: SchemaChangeStatus
    version: int | None = None
    """Set when the status becomes applied; unique among the applied schema changes of the branch."""

    summary: str
    format_version: int
    applied_at: str | None = None
    """The timestamp of the graph writes of the application that applied it."""


class SchemaChangeOperation(StandardNode):
    """One stored operation of a schema change; the operations apply in the order of `position`."""

    position: int
    operation_type: SchemaOperationType
    kind: str
    node_type: SchemaOperationNodeType | None = None
    section: SchemaOperationSection | None = None
    element_name: str | None = None
    property_name: str | None = None
    value: str | None = None
    """JSON text, so that the JSON value `null` is apart from a value that is not set."""

    previous_value: str | None = None
    """JSON text, so that the JSON value `null` is apart from a value that is not set."""


class SchemaChangeApplication(StandardNode):
    """One time a schema change was applied to a branch."""

    branch: str
    status: SchemaChangeApplicationStatus
    at: str
    """The timestamp of every graph write of this application."""

    error: str | None = None


class SchemaChangeMigration(StandardNode):
    """One migration that an application ran, identified inside its application by `position`."""

    position: int
    migration_name: str
    path_type: SchemaPathType
    schema_kind: str
    field_name: str | None = None
    property_name: str | None = None
    status: SchemaChangeMigrationStatus
    nbr_migrations_executed: int | None = None
    errors: list[str] = Field(default_factory=list)
