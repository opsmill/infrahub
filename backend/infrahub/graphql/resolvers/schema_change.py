"""Resolvers of the fields of a schema change that read through the loaders of its request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.path import SchemaPath
from infrahub.core.schema_change.constants import (
    SCHEMA_CHANGE_OPERATIONS_DEFAULT_LIMIT,
    SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT,
)
from infrahub.core.schema_change.operations import build_schema_change_name
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from datetime import datetime

    from graphql import GraphQLResolveInfo

    from infrahub.core.schema_change.history_reader import (
        SchemaChangeApplicationRecord,
        SchemaChangeHistoryEntry,
        StoredSchemaOperation,
    )
    from infrahub.core.schema_change.models import SchemaChange, SchemaChangeMigration
    from infrahub.graphql.loaders.schema_change import SchemaChangeLoaders


@dataclass(frozen=True)
class PageArguments:
    limit: int
    offset: int


def validate_page_arguments(
    *, limit: int | None, offset: int | None, default_limit: int, max_limit: int
) -> PageArguments:
    """Return the page that the arguments ask for, with the default limit when none is given.

    Raises:
        ValidationError: When the limit is below 1 or above `max_limit`, or the offset is below 0.

    """
    page_limit = default_limit if limit is None else limit
    page_offset = 0 if offset is None else offset
    if page_limit < 1:
        raise ValidationError("limit must be >= 1")
    if page_limit > max_limit:
        raise ValidationError(f"limit must be <= {max_limit}")
    if page_offset < 0:
        raise ValidationError("offset must be >= 0")
    return PageArguments(limit=page_limit, offset=page_offset)


@dataclass(frozen=True)
class SchemaChangeNodeValue:
    """A schema change as its GraphQL node reads it, with the loaders of its request."""

    id: str
    name: str
    summary: str
    version: int | None
    status: str
    branch: str
    format_version: int
    created_at: datetime | None
    updated_at: datetime | None
    applied_at: datetime | None
    parent: dict[str, Any] | None
    loaders: SchemaChangeLoaders


def _to_datetime(value: str | None) -> datetime | None:
    return Timestamp(value).to_datetime() if value is not None else None


def _schema_change_name(schema_change: SchemaChange) -> str:
    return build_schema_change_name(version=schema_change.version, summary=schema_change.summary)


def _parent_to_graphql(parent: SchemaChange) -> dict[str, Any]:
    return {
        "id": str(parent.get_uuid()),
        "name": _schema_change_name(schema_change=parent),
        "version": parent.version,
        "branch": parent.branch,
    }


def build_schema_change_node(entry: SchemaChangeHistoryEntry, loaders: SchemaChangeLoaders) -> SchemaChangeNodeValue:
    schema_change = entry.schema_change
    return SchemaChangeNodeValue(
        id=str(schema_change.get_uuid()),
        name=_schema_change_name(schema_change=schema_change),
        summary=schema_change.summary,
        version=schema_change.version,
        status=schema_change.status.value,
        branch=schema_change.branch,
        format_version=schema_change.format_version,
        created_at=_to_datetime(schema_change.created_at),
        updated_at=_to_datetime(schema_change.updated_at),
        applied_at=_to_datetime(schema_change.applied_at),
        parent=_parent_to_graphql(parent=entry.parent) if entry.parent is not None else None,
        loaders=loaders,
    )


def _operation_to_graphql(stored: StoredSchemaOperation) -> dict[str, Any]:
    operation = stored.operation
    return {
        "position": stored.position,
        "operation_type": operation.operation_type.value,
        "kind": operation.kind,
        "node_type": operation.node_type.value if operation.node_type is not None else None,
        "section": operation.section.value if operation.section is not None else None,
        "element_name": operation.element_name,
        "property_name": operation.property_name,
        "value": operation.value,
        "previous_value": operation.previous_value,
    }


def _migration_to_graphql(migration: SchemaChangeMigration) -> dict[str, Any]:
    path = SchemaPath(
        path_type=migration.path_type,
        schema_kind=migration.schema_kind,
        field_name=migration.field_name,
        property_name=migration.property_name,
    )
    return {
        "id": str(migration.get_uuid()),
        "position": migration.position,
        "migration_name": migration.migration_name,
        "path": path.get_path(),
        "path_type": migration.path_type.value,
        "schema_kind": migration.schema_kind,
        "field_name": migration.field_name,
        "property_name": migration.property_name,
        "status": migration.status.value,
        "nbr_migrations_executed": migration.nbr_migrations_executed,
        "errors": migration.errors,
        "updated_at": _to_datetime(migration.updated_at),
    }


def _application_to_graphql(record: SchemaChangeApplicationRecord) -> dict[str, Any]:
    application = record.application
    return {
        "id": str(application.get_uuid()),
        "status": application.status.value,
        "branch": application.branch,
        "at": _to_datetime(application.at),
        "error": application.error,
        "created_at": _to_datetime(application.created_at),
        "updated_at": _to_datetime(application.updated_at),
        "migrations": [_migration_to_graphql(migration=migration) for migration in record.migrations],
    }


async def schema_change_operations_resolver(
    parent: SchemaChangeNodeValue,
    info: GraphQLResolveInfo,  # noqa: ARG001
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Resolve one page of the operations of a schema change.

    Raises:
        ValidationError: When the limit or the offset is out of range.

    """
    page = validate_page_arguments(
        limit=limit,
        offset=offset,
        default_limit=SCHEMA_CHANGE_OPERATIONS_DEFAULT_LIMIT,
        max_limit=SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT,
    )
    operation_page = await parent.loaders.operations(limit=page.limit, offset=page.offset).load(parent.id)
    return {
        "count": operation_page.count,
        "edges": [{"node": _operation_to_graphql(stored=stored)} for stored in operation_page.operations],
    }


async def schema_change_applications_resolver(
    parent: SchemaChangeNodeValue,
    info: GraphQLResolveInfo,  # noqa: ARG001
) -> list[dict[str, Any]]:
    """Resolve the applications of a schema change, each with its migration records."""
    records = await parent.loaders.applications.load(parent.id)
    return [_application_to_graphql(record=record) for record in records]
