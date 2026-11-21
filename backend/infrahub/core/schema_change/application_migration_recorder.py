from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from infrahub.core.schema_change.enums import SchemaChangeMigrationStatus
from infrahub.core.schema_change.migration_recorder import MigrationRecorder
from infrahub.core.schema_change.record_errors import RECORD_WRITE_ERRORS
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
    from infrahub.core.models import SchemaUpdateMigrationInfo

log = get_logger()


class MigrationRecordStore(Protocol):
    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> None: ...

    async def set_migration_records_status(
        self,
        *,
        application_id: str,
        positions: Sequence[int],
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
        self._recorded_positions: frozenset[int] = frozenset()
        # The migrations run concurrently, and the store's database session runs one query at a time.
        self._write_lock = asyncio.Lock()

    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None:
        try:
            async with self._write_lock:
                await self.store.create_migration_records(application_id=self.application_id, migrations=migrations)
        except RECORD_WRITE_ERRORS:
            log.warning(
                "Could not create the migration records of an application",
                application_id=self.application_id,
                exc_info=True,
            )
        else:
            self._recorded_positions = frozenset(range(len(migrations)))

    async def migration_started(self, *, position: int) -> None:
        if position not in self._recorded_positions:
            return
        try:
            async with self._write_lock:
                await self.store.set_migration_records_status(
                    application_id=self.application_id,
                    positions=[position],
                    status=SchemaChangeMigrationStatus.RUNNING,
                    nbr_migrations_executed=None,
                    errors=[],
                )
        except RECORD_WRITE_ERRORS:
            log.warning(
                "Could not set the migration record of a migration to running",
                application_id=self.application_id,
                position=position,
                exc_info=True,
            )

    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None:
        if position not in self._recorded_positions:
            return
        status = SchemaChangeMigrationStatus.FAILED if result.errors else SchemaChangeMigrationStatus.APPLIED
        try:
            async with self._write_lock:
                await self.store.set_migration_records_status(
                    application_id=self.application_id,
                    positions=[position],
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
