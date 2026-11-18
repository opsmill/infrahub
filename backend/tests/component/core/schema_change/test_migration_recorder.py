from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
from infrahub.core.schema_change.enums import SchemaChangeMigrationStatus, SchemaChangeStatus
from infrahub.core.schema_change.factory import build_migration_recorder
from tests.helpers.schema_change import (
    BranchHistorySeed,
    SeededSchemaChange,
    attribute_migration,
    read_applications_with_migrations,
    seed_schema_change_history,
)

if TYPE_CHECKING:
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "main"
MIGRATION_ERROR = "Unable to convert the value of 2 nodes"
MISSING_APPLICATION_ID = "5c8e1f2d-7a3b-4e96-8d10-b2f4a6c9e357"

MIGRATIONS: list[SchemaUpdateMigrationInfo] = [
    attribute_migration(migration_name="node.attribute.add", field_name="color"),
    attribute_migration(migration_name="attribute.kind.update", field_name="name"),
    attribute_migration(migration_name="node.attribute.add", field_name="color"),
]


async def _seed_application(db: InfrahubDatabase) -> SeededSchemaChange:
    history = await seed_schema_change_history(
        db=db, branches=[BranchHistorySeed(branch=BRANCH_NAME, changes=[SchemaChangeStatus.RUNNING])]
    )
    return history.schema_changes[0]


async def _read_migrations(
    db: InfrahubDatabase, schema_change: SeededSchemaChange
) -> list[tuple[int, str, str | None, SchemaChangeMigrationStatus, int | None, list[str]]]:
    applications = await read_applications_with_migrations(db=db, schema_change_ids=[schema_change.id])
    (record,) = applications[schema_change.id]
    return [
        (
            migration.position,
            migration.migration_name,
            migration.field_name,
            migration.status,
            migration.nbr_migrations_executed,
            list(migration.errors),
        )
        for migration in record.migrations
    ]


def _result(
    migration: SchemaUpdateMigrationInfo, nbr_migrations_executed: int, errors: list[str] | None = None
) -> SchemaMigrationPathResponseData:
    return SchemaMigrationPathResponseData(
        migration_name=migration.migration_name,
        schema_path=migration.path,
        nbr_migrations_executed=nbr_migrations_executed,
        errors=errors or [],
    )


async def test_register_creates_waiting_records(db: InfrahubDatabase, empty_database: None) -> None:
    schema_change = await _seed_application(db=db)
    recorder = build_migration_recorder(db=db, application_id=schema_change.application_id)

    await recorder.register(migrations=MIGRATIONS)

    assert await _read_migrations(db=db, schema_change=schema_change) == [
        (0, "node.attribute.add", "color", SchemaChangeMigrationStatus.WAITING, None, []),
        (1, "attribute.kind.update", "name", SchemaChangeMigrationStatus.WAITING, None, []),
        (2, "node.attribute.add", "color", SchemaChangeMigrationStatus.WAITING, None, []),
    ]


async def test_migration_started_sets_only_the_record_at_its_position_to_running(
    db: InfrahubDatabase, empty_database: None
) -> None:
    schema_change = await _seed_application(db=db)
    recorder = build_migration_recorder(db=db, application_id=schema_change.application_id)
    await recorder.register(migrations=MIGRATIONS)

    await recorder.migration_started(position=1)

    assert [status for _, _, _, status, _, _ in await _read_migrations(db=db, schema_change=schema_change)] == [
        SchemaChangeMigrationStatus.WAITING,
        SchemaChangeMigrationStatus.RUNNING,
        SchemaChangeMigrationStatus.WAITING,
    ]


async def test_migration_ended_without_error_sets_applied_and_stores_a_count_of_zero(
    db: InfrahubDatabase, empty_database: None
) -> None:
    schema_change = await _seed_application(db=db)
    recorder = build_migration_recorder(db=db, application_id=schema_change.application_id)
    await recorder.register(migrations=MIGRATIONS)
    for position in range(len(MIGRATIONS)):
        await recorder.migration_started(position=position)

    await recorder.migration_ended(position=1, result=_result(MIGRATIONS[1], nbr_migrations_executed=0))

    assert await _read_migrations(db=db, schema_change=schema_change) == [
        (0, "node.attribute.add", "color", SchemaChangeMigrationStatus.RUNNING, None, []),
        (1, "attribute.kind.update", "name", SchemaChangeMigrationStatus.APPLIED, 0, []),
        (2, "node.attribute.add", "color", SchemaChangeMigrationStatus.RUNNING, None, []),
    ]


async def test_migration_ended_with_errors_sets_failed_and_stores_the_errors(
    db: InfrahubDatabase, empty_database: None
) -> None:
    schema_change = await _seed_application(db=db)
    recorder = build_migration_recorder(db=db, application_id=schema_change.application_id)
    await recorder.register(migrations=MIGRATIONS)
    for position in range(len(MIGRATIONS)):
        await recorder.migration_started(position=position)

    await recorder.migration_ended(
        position=1, result=_result(MIGRATIONS[1], nbr_migrations_executed=2, errors=[MIGRATION_ERROR])
    )

    assert (await _read_migrations(db=db, schema_change=schema_change))[1] == (
        1,
        "attribute.kind.update",
        "name",
        SchemaChangeMigrationStatus.FAILED,
        2,
        [MIGRATION_ERROR],
    )


async def test_migrations_with_the_same_name_and_path_are_updated_by_position(
    db: InfrahubDatabase, empty_database: None
) -> None:
    schema_change = await _seed_application(db=db)
    recorder = build_migration_recorder(db=db, application_id=schema_change.application_id)
    await recorder.register(migrations=MIGRATIONS)
    for position in range(len(MIGRATIONS)):
        await recorder.migration_started(position=position)

    await recorder.migration_ended(position=2, result=_result(MIGRATIONS[2], nbr_migrations_executed=5))
    await recorder.migration_ended(
        position=0, result=_result(MIGRATIONS[0], nbr_migrations_executed=1, errors=[MIGRATION_ERROR])
    )

    assert await _read_migrations(db=db, schema_change=schema_change) == [
        (0, "node.attribute.add", "color", SchemaChangeMigrationStatus.FAILED, 1, [MIGRATION_ERROR]),
        (1, "attribute.kind.update", "name", SchemaChangeMigrationStatus.RUNNING, None, []),
        (2, "node.attribute.add", "color", SchemaChangeMigrationStatus.APPLIED, 5, []),
    ]


async def test_recorder_without_application_creates_no_record(db: InfrahubDatabase, empty_database: None) -> None:
    schema_change = await _seed_application(db=db)
    recorder = build_migration_recorder(db=db, application_id=None)

    await recorder.register(migrations=MIGRATIONS)
    for position in range(len(MIGRATIONS)):
        await recorder.migration_started(position=position)
    await recorder.migration_ended(position=0, result=_result(MIGRATIONS[0], nbr_migrations_executed=1))

    results = await db.execute_query(
        query="MATCH (record:SchemaChangeMigration) RETURN count(record) AS nbr_records",
        name="test_count_migration_records",
    )
    assert results[0].get("nbr_records") == 0
    assert await _read_migrations(db=db, schema_change=schema_change) == []


async def test_recorder_of_a_missing_application_creates_no_record_and_does_not_raise(
    db: InfrahubDatabase, empty_database: None
) -> None:
    recorder = build_migration_recorder(db=db, application_id=MISSING_APPLICATION_ID)

    await recorder.register(migrations=MIGRATIONS)
    for position in range(len(MIGRATIONS)):
        await recorder.migration_started(position=position)
    await recorder.migration_ended(position=0, result=_result(MIGRATIONS[0], nbr_migrations_executed=1))

    results = await db.execute_query(
        query="MATCH (record:SchemaChangeMigration) RETURN count(record) AS nbr_records",
        name="test_count_migration_records",
    )
    assert results[0].get("nbr_records") == 0
