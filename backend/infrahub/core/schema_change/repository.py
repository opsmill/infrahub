from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub_sdk.uuidt import UUIDT

from infrahub.core.query import Query, QueryType
from infrahub.core.schema_change.constants import SCHEMA_OPERATION_FORMAT_VERSION
from infrahub.core.schema_change.cypher_names import CYPHER_NAMES
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
)
from infrahub.core.schema_change.models import SchemaChange, SchemaChangeApplication, SchemaChangeMigration
from infrahub.core.schema_change.operations import build_schema_change_summary
from infrahub.core.timestamp import Timestamp
from infrahub.database import retry_db_transaction

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.record_serializer import RecordProperties, SchemaChangeRecordSerializer
    from infrahub.database import InfrahubDatabase


class SchemaChangeCreateQuery(Query):
    """Create a schema change, its operations and one application."""

    name = "schema-change-create"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        schema_change_properties: RecordProperties,
        operation_properties: Sequence[RecordProperties],
        application_properties: RecordProperties,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.params["schema_change"] = schema_change_properties
        self.params["operations"] = list(operation_properties)
        self.params["application"] = application_properties

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        CREATE (schema_change:%(schema_change_label)s $schema_change)
        CREATE (application:%(application_label)s $application)
        CREATE (schema_change)-[:%(has_application)s]->(application)
        WITH schema_change
        CALL (schema_change) {
            UNWIND $operations AS operation
            CREATE (stored_operation:%(operation_label)s)
            SET stored_operation = operation
            CREATE (schema_change)-[:%(has_operation)s]->(stored_operation)
        }
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)


class SchemaChangeMigrationCreateQuery(Query):
    """Create the migration records of an application."""

    name = "schema-change-migration-create"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(self, application_id: str, migration_properties: Sequence[RecordProperties], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["application_id"] = application_id
        self.params["migrations"] = list(migration_properties)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (application:%(application_label)s {uuid: $application_id})
        CALL (application) {
            UNWIND $migrations AS migration
            CREATE (record:%(migration_label)s)
            SET record = migration
            CREATE (application)-[:%(has_migration)s]->(record)
        }
        RETURN application.uuid AS application_id
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["application_id"]


class SchemaChangeMigrationStatusUpdateQuery(Query):
    """Set the status, the result and the errors of the migration records of an application at the positions given."""

    name = "schema-change-migration-status-update"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        application_id: str,
        positions: Sequence[int],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
        updated_at: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.params["application_id"] = application_id
        self.params["positions"] = list(positions)
        self.params["status"] = status.value
        self.params["nbr_migrations_executed"] = nbr_migrations_executed
        self.params["errors"] = list(errors)
        self.params["updated_at"] = updated_at

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (:%(application_label)s {uuid: $application_id})-[:%(has_migration)s]->(record:%(migration_label)s)
        WHERE record.position IN $positions
        SET record.status = $status,
            record.nbr_migrations_executed = $nbr_migrations_executed,
            record.errors = $errors,
            record.updated_at = $updated_at
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)


class SchemaChangeMarkAppliedQuery(Query):
    """Set a schema change and its application to applied, with the version, the time and the parent."""

    name = "schema-change-mark-applied"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(
        self,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: str,
        updated_at: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.parent_id = parent_id
        self.params["schema_change_id"] = schema_change_id
        self.params["application_id"] = application_id
        self.params["parent_id"] = parent_id
        self.params["version"] = version
        self.params["applied_at"] = applied_at
        self.params["updated_at"] = updated_at
        self.params["updated_by"] = self.user_id
        self.params["schema_change_status"] = SchemaChangeStatus.APPLIED.value
        self.params["application_status"] = SchemaChangeApplicationStatus.APPLIED.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query(
            """
            MATCH (schema_change:%(schema_change_label)s {uuid: $schema_change_id})
                -[:%(has_application)s]->(application:%(application_label)s {uuid: $application_id})
            """
            % CYPHER_NAMES
        )
        if self.parent_id is not None:
            self.add_to_query("MATCH (parent:%(schema_change_label)s {uuid: $parent_id})" % CYPHER_NAMES)
        self.add_to_query(
            """
            SET schema_change.status = $schema_change_status,
                schema_change.version = $version,
                schema_change.applied_at = $applied_at,
                schema_change.updated_at = $updated_at,
                schema_change.updated_by = $updated_by,
                application.status = $application_status,
                application.updated_at = $updated_at,
                application.updated_by = $updated_by
            """
        )
        if self.parent_id is not None:
            self.add_to_query("CREATE (schema_change)-[:%(has_parent)s]->(parent)" % CYPHER_NAMES)
        self.add_to_query("RETURN schema_change.uuid AS schema_change_id")
        self.return_labels = ["schema_change_id"]


class SchemaChangeMarkFailedQuery(Query):
    """Set a schema change and its application to failed, and close the migration records of the application.

    A waiting migration record becomes cancelled, and a running one failed with the error added to its errors; a failed
    one stays failed. An applied one becomes rolled back with `rolled_back`, and stays applied without it. With
    `only_if_running`, a schema change that is not running is left as it is and the query returns no row.
    """

    name = "schema-change-mark-failed"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(
        self,
        schema_change_id: str,
        application_id: str,
        error: str,
        updated_at: str,
        only_if_running: bool,
        rolled_back: bool,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.only_if_running = only_if_running
        # A schema change that is no longer running gives no row, which is an answer and not an error.
        self.raise_error_if_empty = not only_if_running
        self.params["running_schema_change_status"] = SchemaChangeStatus.RUNNING.value
        self.params["schema_change_id"] = schema_change_id
        self.params["application_id"] = application_id
        self.params["error"] = error
        self.params["updated_at"] = updated_at
        self.params["updated_by"] = self.user_id
        self.params["schema_change_status"] = SchemaChangeStatus.FAILED.value
        self.params["application_status"] = SchemaChangeApplicationStatus.FAILED.value
        self.params["applied_migration_status"] = SchemaChangeMigrationStatus.APPLIED.value
        self.params["rolled_back_migration_status"] = SchemaChangeMigrationStatus.ROLLED_BACK.value
        self.params["waiting_migration_status"] = SchemaChangeMigrationStatus.WAITING.value
        self.params["cancelled_migration_status"] = SchemaChangeMigrationStatus.CANCELLED.value
        self.params["running_migration_status"] = SchemaChangeMigrationStatus.RUNNING.value
        self.params["failed_migration_status"] = SchemaChangeMigrationStatus.FAILED.value
        closed_migration_statuses = [SchemaChangeMigrationStatus.WAITING, SchemaChangeMigrationStatus.RUNNING]
        if rolled_back:
            closed_migration_statuses.append(SchemaChangeMigrationStatus.APPLIED)
        self.params["closed_migration_statuses"] = [status.value for status in closed_migration_statuses]

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query(
            """
        MATCH (schema_change:%(schema_change_label)s {uuid: $schema_change_id})
            -[:%(has_application)s]->(application:%(application_label)s {uuid: $application_id})
        """
            % CYPHER_NAMES
        )
        if self.only_if_running:
            self.add_to_query("WHERE schema_change.status = $running_schema_change_status")
        query = (
            """
        SET schema_change.status = $schema_change_status,
            schema_change.updated_at = $updated_at,
            schema_change.updated_by = $updated_by,
            application.status = $application_status,
            application.error = $error,
            application.updated_at = $updated_at,
            application.updated_by = $updated_by
        WITH schema_change, application
        CALL (application) {
            MATCH (application)-[:%(has_migration)s]->(record:%(migration_label)s)
            WHERE record.status IN $closed_migration_statuses
            WITH record, record.status = $running_migration_status AS was_running
            SET record.status = CASE record.status
                    WHEN $applied_migration_status THEN $rolled_back_migration_status
                    WHEN $waiting_migration_status THEN $cancelled_migration_status
                    ELSE $failed_migration_status
                END,
                record.errors = CASE WHEN was_running THEN coalesce(record.errors, []) + $error ELSE record.errors END,
                record.updated_at = $updated_at
        }
        RETURN schema_change.uuid AS schema_change_id
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id"]

    def get_data(self) -> bool:
        """Return whether the schema change was set to failed."""
        return self.get_result() is not None


@dataclass(frozen=True)
class SchemaChangeVersionQueryResult:
    schema_change_id: str
    version: int


class SchemaChangeHighestVersionQuery(Query):
    """Return the applied schema change with the highest version on a branch."""

    name = "schema-change-highest-version"
    type = QueryType.READ
    insert_return = False

    def __init__(self, branch_name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = 1
        self.params["branch_name"] = branch_name
        self.params["applied_status"] = SchemaChangeStatus.APPLIED.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (schema_change:%(schema_change_label)s {branch: $branch_name, status: $applied_status})
        RETURN schema_change.uuid AS schema_change_id, schema_change.version AS version
        ORDER BY schema_change.version DESC, schema_change.uuid
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "version"]

    def get_data(self) -> SchemaChangeVersionQueryResult | None:
        result = self.get_result()
        if result is None:
            return None
        return SchemaChangeVersionQueryResult(
            schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
            version=result.get_as_type(label="version", return_type=int),
        )


class SchemaChangeHighestVersionAtQuery(Query):
    """Return the applied schema change with the highest version on a branch, among those applied at or before a time."""

    name = "schema-change-highest-version-at"
    type = QueryType.READ
    insert_return = False

    def __init__(self, branch_name: str, applied_at_or_before: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = 1
        self.params["branch_name"] = branch_name
        self.params["applied_at_or_before"] = applied_at_or_before
        self.params["applied_status"] = SchemaChangeStatus.APPLIED.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (schema_change:%(schema_change_label)s {branch: $branch_name, status: $applied_status})
        WHERE schema_change.applied_at <= $applied_at_or_before
        RETURN schema_change.uuid AS schema_change_id, schema_change.version AS version
        ORDER BY schema_change.version DESC, schema_change.uuid
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "version"]

    def get_data(self) -> SchemaChangeVersionQueryResult | None:
        result = self.get_result()
        if result is None:
            return None
        return SchemaChangeVersionQueryResult(
            schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
            version=result.get_as_type(label="version", return_type=int),
        )


class SchemaChangeDeleteByBranchQuery(Query):
    """Delete the schema changes of a branch with their operations, applications and migration records.

    The records are deleted in batches that each commit on their own, from the migration records up
    to the schema changes, so a deletion that stops part way leaves no record that its schema change
    does not reach, and running it again deletes the rest. It needs an auto-commit transaction.
    """

    name = "schema-change-delete-by-branch"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    def __init__(self, branch_name: str, batch_size: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["branch_name"] = branch_name
        self.params["batch_size"] = batch_size

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (:%(schema_change_label)s {branch: $branch_name})-[:%(has_application)s]->(:%(application_label)s)
            -[:%(has_migration)s]->(migration:%(migration_label)s)
        CALL (migration) {
            DETACH DELETE migration
        } IN TRANSACTIONS OF $batch_size ROWS
        WITH count(*) AS nbr_migrations
        MATCH (:%(schema_change_label)s {branch: $branch_name})-[:%(has_operation)s]->(operation:%(operation_label)s)
        CALL (operation) {
            DETACH DELETE operation
        } IN TRANSACTIONS OF $batch_size ROWS
        WITH count(*) AS nbr_operations
        MATCH (:%(schema_change_label)s {branch: $branch_name})-[:%(has_application)s]->(application:%(application_label)s)
        CALL (application) {
            DETACH DELETE application
        } IN TRANSACTIONS OF $batch_size ROWS
        WITH count(*) AS nbr_applications
        MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})
        CALL (schema_change) {
            DETACH DELETE schema_change
        } IN TRANSACTIONS OF $batch_size ROWS
        RETURN count(*) AS nbr_deleted
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["nbr_deleted"]

    def get_data(self) -> int:
        """Return the number of schema changes deleted."""
        result = self.get_result()
        if result is None:
            return 0
        return result.get_as_type(label="nbr_deleted", return_type=int)


@dataclass(frozen=True)
class CreatedSchemaChange:
    schema_change_id: str
    application_id: str


@dataclass(frozen=True)
class AppliedSchemaChangeVersion:
    schema_change_id: str
    version: int


class SchemaChangeRepository:
    """The writes of the schema change records, the reads of the versions of a branch, and the deletion of a branch's records.

    The ID of each record is its `uuid`, which is time-ordered. Each write is one statement; outside a transaction,
    a write that Neo4j rejects with a transient error runs again.
    """

    def __init__(self, db: InfrahubDatabase, serializer: SchemaChangeRecordSerializer) -> None:
        self.db = db
        self.serializer = serializer

    async def _write(self, query: Query) -> None:
        if self.db.is_transaction:
            # A failed statement aborts the caller's transaction, so only the caller that owns it can run it again.
            await query.execute(db=self.db)
            return
        await self._write_with_retry(query=query)

    @retry_db_transaction(name="schema_change_record_write")
    async def _write_with_retry(self, query: Query) -> None:
        await query.execute(db=self.db)

    async def create_schema_change(
        self, *, branch: str, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> CreatedSchemaChange:
        """Create a running schema change with its operations, and its running application at `at`.

        Raises:
            ValueError: When `operations` is empty.

        """
        created_at = Timestamp().to_string()
        schema_change = SchemaChange(
            uuid=str(UUIDT()),
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
            self.serializer.operation_to_record(
                uuid=str(UUIDT()), position=position, operation=operation, created_at=created_at, created_by=user_id
            )
            for position, operation in enumerate(operations)
        ]
        application = SchemaChangeApplication(
            uuid=str(UUIDT()),
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
            schema_change_properties=self.serializer.schema_change_to_properties(record=schema_change),
            operation_properties=[
                self.serializer.operation_to_properties(record=operation) for operation in stored_operations
            ],
            application_properties=self.serializer.application_to_properties(record=application),
        )
        await self._write(query=query)
        return CreatedSchemaChange(schema_change_id=schema_change.uuid, application_id=application.uuid)

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
        await self._write(query=query)

    async def mark_failed(self, *, schema_change_id: str, application_id: str, error: str, user_id: str) -> None:
        """Set a schema change and its application to failed, and close its migration records.

        An applied migration record becomes rolled back, a waiting one cancelled, and a running one failed with the
        error added to its errors; a failed one stays failed.

        Raises:
            QueryError: When the schema change or its application is not stored.

        """
        query = await SchemaChangeMarkFailedQuery.init(
            db=self.db,
            schema_change_id=schema_change_id,
            application_id=application_id,
            error=error,
            updated_at=Timestamp().to_string(),
            only_if_running=False,
            rolled_back=True,
            user_id=user_id,
        )
        await self._write(query=query)

    async def mark_failed_if_running(
        self, *, schema_change_id: str, application_id: str, error: str, user_id: str
    ) -> bool:
        """Set a schema change and its application to failed, only while the schema change is running, for a load that was not rolled back.

        An applied migration record stays applied, a waiting one becomes cancelled, and a running one failed with the
        error added to its errors.

        Returns:
            Whether the schema change was set to failed; False when it is no longer running or is not stored.

        """
        query = await SchemaChangeMarkFailedQuery.init(
            db=self.db,
            schema_change_id=schema_change_id,
            application_id=application_id,
            error=error,
            updated_at=Timestamp().to_string(),
            only_if_running=True,
            rolled_back=False,
            user_id=user_id,
        )
        await self._write(query=query)
        return query.get_data()

    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> None:
        """Create one waiting record for each migration, with the index of the migration as its position.

        Raises:
            QueryError: When the application is not stored.

        """
        if not migrations:
            return

        created_at = Timestamp().to_string()
        records = [
            SchemaChangeMigration(
                uuid=str(UUIDT()),
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
            db=self.db,
            application_id=application_id,
            migration_properties=[self.serializer.migration_to_properties(record=record) for record in records],
        )
        await self._write(query=query)

    async def set_migration_records_status(
        self,
        *,
        application_id: str,
        positions: Sequence[int],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None:
        if not positions:
            return

        query = await SchemaChangeMigrationStatusUpdateQuery.init(
            db=self.db,
            application_id=application_id,
            positions=positions,
            status=status,
            nbr_migrations_executed=nbr_migrations_executed,
            errors=errors,
            updated_at=Timestamp().to_string(),
        )
        await self._write(query=query)

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

    async def delete_branch_schema_changes(self, *, branch: str, batch_size: int) -> int:
        """Delete the schema changes of a branch with all their records, and return the number of schema changes deleted.

        The deletion must run outside a transaction, because it commits each batch of `batch_size` records on its own.
        """
        query = await SchemaChangeDeleteByBranchQuery.init(db=self.db, branch_name=branch, batch_size=batch_size)
        await query.execute(db=self.db)
        return query.get_data()
