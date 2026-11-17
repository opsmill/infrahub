from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.query.schema_change import (
    SchemaChangeCreateQuery,
    SchemaChangeHighestVersionAtQuery,
    SchemaChangeHighestVersionQuery,
    SchemaChangeMarkAppliedQuery,
    SchemaChangeMarkFailedQuery,
    SchemaChangeMigrationCreateQuery,
    SchemaChangeMigrationStatusUpdateQuery,
)
from infrahub.core.schema_change.constants import SCHEMA_OPERATION_FORMAT_VERSION
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
)
from infrahub.core.schema_change.models import (
    SchemaChange,
    SchemaChangeApplication,
    SchemaChangeMigration,
    SchemaChangeOperation,
)
from infrahub.core.schema_change.operations import build_schema_change_summary
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class CreatedSchemaChange:
    schema_change_id: str
    application_id: str


@dataclass(frozen=True)
class AppliedSchemaChangeVersion:
    schema_change_id: str
    version: int


class SchemaChangeRepository:
    """The writes of the schema change records, and the reads of the versions of a branch.

    The ID of a schema change and of an application is its `uuid` as text; the ID of a migration
    record is its element ID.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def create_schema_change(
        self, *, branch: str, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> CreatedSchemaChange:
        """Create a running schema change with its operations, and its running application at `at`.

        Raises:
            ValueError: When `operations` is empty.

        """
        created_at = Timestamp().to_string()
        schema_change = SchemaChange(
            branch=branch,
            status=SchemaChangeStatus.RUNNING,
            summary=build_schema_change_summary(operations=operations),
            format_version=SCHEMA_OPERATION_FORMAT_VERSION,
            created_at=created_at,
            created_by=user_id,
            updated_at=created_at,
            updated_by=user_id,
        )
        stored_operations = [
            self._to_stored_operation(position=position, operation=operation, created_at=created_at, user_id=user_id)
            for position, operation in enumerate(operations)
        ]
        application = SchemaChangeApplication(
            branch=branch,
            status=SchemaChangeApplicationStatus.RUNNING,
            at=at.to_string(),
            created_at=created_at,
            created_by=user_id,
            updated_at=created_at,
            updated_by=user_id,
        )

        query = await SchemaChangeCreateQuery.init(
            db=self.db,
            schema_change_properties=schema_change.to_db(),
            operation_properties=[operation.to_db() for operation in stored_operations],
            application_properties=application.to_db(),
        )
        await query.execute(db=self.db)
        created = query.get_data()
        return CreatedSchemaChange(schema_change_id=created.schema_change_id, application_id=created.application_id)

    async def mark_applied(
        self,
        *,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: Timestamp,
        user_id: str,
    ) -> None:
        """Set a schema change and its application to applied, and link the schema change to its parent.

        Raises:
            QueryError: When the schema change, its application or the parent is not stored.

        """
        query = await SchemaChangeMarkAppliedQuery.init(
            db=self.db,
            schema_change_id=schema_change_id,
            application_id=application_id,
            version=version,
            parent_id=parent_id,
            applied_at=applied_at.to_string(),
            updated_at=Timestamp().to_string(),
            user_id=user_id,
        )
        await query.execute(db=self.db)

    async def mark_failed(self, *, schema_change_id: str, application_id: str, error: str, user_id: str) -> None:
        """Set a schema change and its application to failed, and its applied migration records to rolled back.

        Raises:
            QueryError: When the schema change or its application is not stored.

        """
        query = await SchemaChangeMarkFailedQuery.init(
            db=self.db,
            schema_change_id=schema_change_id,
            application_id=application_id,
            error=error,
            updated_at=Timestamp().to_string(),
            user_id=user_id,
        )
        await query.execute(db=self.db)

    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> dict[int, str]:
        """Create one waiting record for each migration, and return the record IDs by position.

        Raises:
            QueryError: When the application is not stored.

        """
        if not migrations:
            return {}

        created_at = Timestamp().to_string()
        records = [
            SchemaChangeMigration(
                position=position,
                migration_name=migration.migration_name,
                path_type=migration.path.path_type,
                schema_kind=migration.path.schema_kind,
                field_name=migration.path.field_name,
                property_name=migration.path.property_name,
                status=SchemaChangeMigrationStatus.WAITING,
                created_at=created_at,
                updated_at=created_at,
            )
            for position, migration in enumerate(migrations)
        ]
        query = await SchemaChangeMigrationCreateQuery.init(
            db=self.db, application_id=application_id, migration_properties=[record.to_db() for record in records]
        )
        await query.execute(db=self.db)
        return {created.position: created.record_id for created in query.get_data()}

    async def set_migration_records_status(
        self,
        *,
        record_ids: Sequence[str],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None:
        if not record_ids:
            return

        query = await SchemaChangeMigrationStatusUpdateQuery.init(
            db=self.db,
            record_ids=record_ids,
            status=status,
            nbr_migrations_executed=nbr_migrations_executed,
            errors=errors,
            updated_at=Timestamp().to_string(),
        )
        await query.execute(db=self.db)

    async def get_highest_applied_version(self, *, branch: str) -> AppliedSchemaChangeVersion | None:
        query = await SchemaChangeHighestVersionQuery.init(db=self.db, branch_name=branch)
        await query.execute(db=self.db)
        highest = query.get_data()
        if highest is None:
            return None
        return AppliedSchemaChangeVersion(schema_change_id=highest.schema_change_id, version=highest.version)

    async def get_highest_applied_version_at(self, *, branch: str, at: Timestamp) -> AppliedSchemaChangeVersion | None:
        """Return the applied schema change with the highest version among those whose `applied_at` is at or before `at`."""
        query = await SchemaChangeHighestVersionAtQuery.init(
            db=self.db, branch_name=branch, applied_at_or_before=at.to_string()
        )
        await query.execute(db=self.db)
        highest = query.get_data()
        if highest is None:
            return None
        return AppliedSchemaChangeVersion(schema_change_id=highest.schema_change_id, version=highest.version)

    def _to_stored_operation(
        self, *, position: int, operation: SchemaOperation, created_at: str, user_id: str
    ) -> SchemaChangeOperation:
        return SchemaChangeOperation(
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
            created_by=user_id,
            updated_at=created_at,
            updated_by=user_id,
        )
