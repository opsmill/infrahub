from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from infrahub.core.query.schema_change import (
    SchemaChangeApplicationListQuery,
    SchemaChangeCountQuery,
    SchemaChangeListQuery,
    SchemaChangeOperationPageQuery,
)
from infrahub.core.schema_change.models import (
    SchemaChange,
    SchemaChangeApplication,
    SchemaChangeMigration,
    SchemaChangeOperation,
)
from infrahub.core.schema_change.operations import SchemaOperation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import JsonValue

    from infrahub.core.query.schema_change import (
        SchemaChangeApplicationRecordData,
        SchemaChangeMigrationRecordData,
        SchemaChangeOperationRecordData,
        SchemaChangeRecordData,
    )
    from infrahub.core.schema_change.constants import SchemaChangeStatus
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class SchemaChangeHistoryEntry:
    schema_change: SchemaChange
    parent: SchemaChange | None


@dataclass(frozen=True)
class SchemaChangeHistoryPage:
    count: int
    """The number of schema changes that match, on all pages."""

    entries: list[SchemaChangeHistoryEntry]


@dataclass(frozen=True)
class StoredSchemaOperation:
    position: int
    operation: SchemaOperation


@dataclass(frozen=True)
class SchemaOperationPage:
    count: int
    """The number of operations of the schema change, on all pages."""

    operations: list[StoredSchemaOperation]


@dataclass(frozen=True)
class SchemaChangeApplicationRecord:
    application: SchemaChangeApplication
    migrations: list[SchemaChangeMigration]


class SchemaChangeHistoryReader:
    """The paged reads of the schema change history of a branch.

    The reads for a set of schema changes return a key, the `uuid` of the schema change as text,
    for each ID that names a stored schema change.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def list_schema_changes(
        self, *, branch: str, limit: int, offset: int, statuses: Sequence[SchemaChangeStatus] | None = None
    ) -> SchemaChangeHistoryPage:
        """Return one page of the schema changes of a branch: the applied ones by version, then the others by creation."""
        list_query = await SchemaChangeListQuery.init(
            db=self.db, branch_name=branch, statuses=statuses, limit=limit, offset=offset
        )
        await list_query.execute(db=self.db)
        count_query = await SchemaChangeCountQuery.init(db=self.db, branch_name=branch, statuses=statuses)
        await count_query.execute(db=self.db)

        return SchemaChangeHistoryPage(
            count=count_query.get_data(),
            entries=[
                SchemaChangeHistoryEntry(
                    schema_change=self._to_schema_change(data=row.schema_change),
                    parent=self._to_schema_change(data=row.parent) if row.parent is not None else None,
                )
                for row in list_query.get_data()
            ],
        )

    async def list_operations(
        self, *, schema_change_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaOperationPage]:
        """Return one page of the operations of each schema change, in the order of position."""
        query = await SchemaChangeOperationPageQuery.init(
            db=self.db, schema_change_ids=schema_change_ids, limit=limit, offset=offset
        )
        await query.execute(db=self.db)

        pages: dict[str, SchemaOperationPage] = {}
        for row in query.get_data():
            stored_operations = [self._to_stored_operation(data=data) for data in row.operations]
            pages[row.schema_change_id] = SchemaOperationPage(
                count=row.count,
                operations=[
                    StoredSchemaOperation(position=stored.position, operation=self._to_schema_operation(stored=stored))
                    for stored in stored_operations
                ],
            )
        return pages

    async def list_applications(
        self, *, schema_change_ids: Sequence[str]
    ) -> dict[str, list[SchemaChangeApplicationRecord]]:
        """Return the applications of each schema change, each with its migration records in the order of position."""
        query = await SchemaChangeApplicationListQuery.init(db=self.db, schema_change_ids=schema_change_ids)
        await query.execute(db=self.db)

        applications: dict[str, list[SchemaChangeApplicationRecord]] = {}
        for row in query.get_data():
            records = applications.setdefault(row.schema_change_id, [])
            if row.application is None:
                continue
            records.append(
                SchemaChangeApplicationRecord(
                    application=self._to_application(data=row.application),
                    migrations=[self._to_migration(data=migration) for migration in row.migrations],
                )
            )
        return applications

    def _to_schema_change(self, data: SchemaChangeRecordData) -> SchemaChange:
        return SchemaChange(
            id=data.metadata.db_id,
            uuid=UUID(data.metadata.uuid),
            created_at=data.metadata.created_at,
            created_by=data.metadata.created_by,
            updated_at=data.metadata.updated_at,
            updated_by=data.metadata.updated_by,
            branch=data.branch,
            status=data.status,
            version=data.version,
            summary=data.summary,
            format_version=data.format_version,
            applied_at=data.applied_at,
        )

    def _to_stored_operation(self, data: SchemaChangeOperationRecordData) -> SchemaChangeOperation:
        return SchemaChangeOperation(
            id=data.metadata.db_id,
            uuid=UUID(data.metadata.uuid),
            created_at=data.metadata.created_at,
            created_by=data.metadata.created_by,
            updated_at=data.metadata.updated_at,
            updated_by=data.metadata.updated_by,
            position=data.position,
            operation_type=data.operation_type,
            kind=data.kind,
            node_type=data.node_type,
            section=data.section,
            element_name=data.element_name,
            property_name=data.property_name,
            value=data.value,
            previous_value=data.previous_value,
        )

    def _to_schema_operation(self, stored: SchemaChangeOperation) -> SchemaOperation:
        """Build the operation back, setting `value` and `previous_value` only when they were stored."""
        fields: dict[str, JsonValue] = {"operation_type": stored.operation_type.value, "kind": stored.kind}
        if stored.node_type is not None:
            fields["node_type"] = stored.node_type.value
        if stored.section is not None:
            fields["section"] = stored.section.value
        if stored.element_name is not None:
            fields["element_name"] = stored.element_name
        if stored.property_name is not None:
            fields["property_name"] = stored.property_name
        if stored.value is not None:
            fields["value"] = json.loads(stored.value)
        if stored.previous_value is not None:
            fields["previous_value"] = json.loads(stored.previous_value)
        return SchemaOperation.model_validate(fields)

    def _to_application(self, data: SchemaChangeApplicationRecordData) -> SchemaChangeApplication:
        return SchemaChangeApplication(
            id=data.metadata.db_id,
            uuid=UUID(data.metadata.uuid),
            created_at=data.metadata.created_at,
            created_by=data.metadata.created_by,
            updated_at=data.metadata.updated_at,
            updated_by=data.metadata.updated_by,
            branch=data.branch,
            status=data.status,
            at=data.at,
            error=data.error,
        )

    def _to_migration(self, data: SchemaChangeMigrationRecordData) -> SchemaChangeMigration:
        return SchemaChangeMigration(
            id=data.metadata.db_id,
            uuid=UUID(data.metadata.uuid),
            created_at=data.metadata.created_at,
            created_by=data.metadata.created_by,
            updated_at=data.metadata.updated_at,
            updated_by=data.metadata.updated_by,
            position=data.position,
            migration_name=data.migration_name,
            path_type=data.path_type,
            schema_kind=data.schema_kind,
            field_name=data.field_name,
            property_name=data.property_name,
            status=data.status,
            nbr_migrations_executed=data.nbr_migrations_executed,
            errors=list(data.errors),
        )
