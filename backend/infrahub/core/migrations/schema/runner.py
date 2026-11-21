from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from infrahub_sdk.batch import InfrahubBatch

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence

    from prefect.logging.loggers import LoggingAdapter

    from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
    from infrahub.core.migrations.schema.scheduler import MigrationScheduler, PositionedMigration
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema_change.migration_recorder import MigrationRecorder


class SchemaPathMigrator(Protocol):
    async def migrate(
        self, migration: SchemaUpdateMigrationInfo, data: SchemaApplyMigrationData
    ) -> SchemaMigrationPathResponseData: ...


class SchemaMigrationRunner:
    """Run the migrations of one schema application in the order of their schedule, and report each one."""

    def __init__(
        self,
        scheduler: MigrationScheduler,
        migrator: SchemaPathMigrator,
        recorder: MigrationRecorder,
        max_concurrent_groups: int,
        log: logging.Logger | LoggingAdapter,
    ) -> None:
        self.scheduler = scheduler
        self.migrator = migrator
        self.recorder = recorder
        self.max_concurrent_groups = max_concurrent_groups
        self.log = log

    async def run(self, data: SchemaApplyMigrationData) -> list[str]:
        """Run the phases one after another, and stop after the first phase that reports an error."""
        if not data.migrations:
            return []

        schedule = self.scheduler.schedule(
            migrations=data.migrations, previous_schema=data.previous_schema, new_schema=data.new_schema
        )
        await self.recorder.register(migrations=[positioned.migration for positioned in schedule.migrations])

        for scheduled_phase in schedule.phases:
            # the groups of a failed phase stop starting migrations, and the run waits for them, so nothing writes after it returns
            stop = asyncio.Event()
            batch = InfrahubBatch(max_concurrent_execution=self.max_concurrent_groups, return_exceptions=True)
            for group in scheduled_phase.groups:
                batch.add(task=self._run_group, group=group, data=data, stop=stop)

            error_messages: list[str] = []
            exceptions: list[Exception] = []
            async for _, outcome in batch.execute():
                if isinstance(outcome, Exception):
                    exceptions.append(outcome)
                else:
                    error_messages.extend(outcome)

            if exceptions:
                raise exceptions[0]
            if error_messages:
                self.log.warning(
                    f"Migrations of phase {scheduled_phase.phase.value} reported errors, skipping the remaining phases"
                )
                return error_messages

        return []

    async def _run_group(
        self, group: Sequence[PositionedMigration], data: SchemaApplyMigrationData, stop: asyncio.Event
    ) -> list[str]:
        for positioned in group:
            if stop.is_set():
                return []
            self.log.info(
                f"Preparing migration for {positioned.migration.migration_name!r} ({positioned.migration.routing_key})"
            )
            await self.recorder.migration_started(position=positioned.position)
            try:
                result = await self.migrator.migrate(migration=positioned.migration, data=data)
            except Exception:
                stop.set()
                raise
            await self.recorder.migration_ended(position=positioned.position, result=result)
            if result.errors:
                stop.set()
                return result.errors
        return []
