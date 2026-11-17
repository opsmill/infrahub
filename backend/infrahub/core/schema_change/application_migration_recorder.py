from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from neo4j.exceptions import Neo4jError

from infrahub.core.schema_change.constants import SchemaChangeMigrationStatus
from infrahub.core.schema_change.migration_recorder import MigrationRecorder
from infrahub.exceptions import DatabaseError, QueryTimeoutError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
    from infrahub.core.models import SchemaUpdateMigrationInfo

log = get_logger()

RECORD_WRITE_ERRORS = (DatabaseError, QueryTimeoutError, Neo4jError)


class MigrationRecordStore(Protocol):
    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> dict[int, str]: ...

    async def set_migration_records_status(
        self,
        *,
        record_ids: Sequence[str],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None: ...


class ApplicationMigrationRecorder(MigrationRecorder):
    """Keep one migration record for each migration of a schema application, identified by its position.

    A record that cannot be written is logged and keeps its earlier status, so the migrations go on.
    """

    def __init__(self, store: MigrationRecordStore, application_id: str) -> None:
        self.store = store
        self.application_id = application_id
        self._record_ids: dict[int, str] = {}

    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None:
        try:
            self._record_ids = await self.store.create_migration_records(
                application_id=self.application_id, migrations=migrations
            )
        except RECORD_WRITE_ERRORS:
            log.warning(
                "Could not create the migration records of an application",
                application_id=self.application_id,
                exc_info=True,
            )

    async def batch_started(self, *, positions: Sequence[int]) -> None:
        record_ids = [self._record_ids[position] for position in positions if position in self._record_ids]
        if not record_ids:
            return
        try:
            await self.store.set_migration_records_status(
                record_ids=record_ids,
                status=SchemaChangeMigrationStatus.RUNNING,
                nbr_migrations_executed=None,
                errors=[],
            )
        except RECORD_WRITE_ERRORS:
            log.warning(
                "Could not set the migration records of a batch to running",
                application_id=self.application_id,
                positions=list(positions),
                exc_info=True,
            )

    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None:
        record_id = self._record_ids.get(position)
        if record_id is None:
            return
        status = SchemaChangeMigrationStatus.FAILED if result.errors else SchemaChangeMigrationStatus.APPLIED
        try:
            await self.store.set_migration_records_status(
                record_ids=[record_id],
                status=status,
                nbr_migrations_executed=result.nbr_migrations_executed,
                errors=result.errors,
            )
        except RECORD_WRITE_ERRORS:
            log.warning(
                "Could not update the migration record of a migration",
                application_id=self.application_id,
                position=position,
                exc_info=True,
            )
