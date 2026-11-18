from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub_sdk.batch import InfrahubBatch
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import DerivedSchemaPair, MigrationInput
from infrahub.core.schema.derived_kinds import get_object_template_kind, get_profile_kind
from infrahub.core.schema_change.factory import build_migration_recorder
from infrahub.workers.dependencies import get_database
from infrahub.workflows.utils import add_branch_tag

from .models import SchemaApplyMigrationData, SchemaMigrationPathResponseData

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence

    from prefect.logging.loggers import LoggingAdapter

    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.path import SchemaPath
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.migration_recorder import MigrationRecorder
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class PositionedMigration:
    position: int
    """The index of the migration in the migrations of the flow message sorted by schema path."""
    migration: SchemaUpdateMigrationInfo


@dataclass(frozen=True)
class PositionedMigrationResult:
    position: int
    result: SchemaMigrationPathResponseData


def get_derived_schema_pairs(
    previous_schema_branch: SchemaBranch,
    new_schema_branch: SchemaBranch,
    previous_node_schema: MainSchemaTypes,
    new_node_schema: MainSchemaTypes | None,
) -> list[DerivedSchemaPair]:
    """Pair up the Profile/Template schemas generated from a node across a schema update."""
    if new_node_schema is None:
        return []

    def pair_up(previous_kind: str, new_kind: str) -> DerivedSchemaPair | None:
        if not previous_schema_branch.has(name=previous_kind) or not new_schema_branch.has(name=new_kind):
            return None
        return DerivedSchemaPair(
            previous=previous_schema_branch.get(name=previous_kind, duplicate=False),
            new=new_schema_branch.get(name=new_kind, duplicate=False),
        )

    pairs = [
        pair_up(
            previous_kind=get_profile_kind(node_kind=previous_node_schema.kind),
            new_kind=get_profile_kind(node_kind=new_node_schema.kind),
        ),
        pair_up(
            previous_kind=get_object_template_kind(node_kind=previous_node_schema.kind),
            new_kind=get_object_template_kind(node_kind=new_node_schema.kind),
        ),
    ]
    return [pair for pair in pairs if pair is not None]


def _migration_sort_key(migration: SchemaUpdateMigrationInfo) -> tuple[str, str, str, str, str]:
    path = migration.path
    return (
        path.schema_kind,
        path.field_name or "",
        path.property_name or "",
        path.path_type.value,
        migration.migration_name,
    )


def position_migrations(migrations: Sequence[SchemaUpdateMigrationInfo]) -> list[PositionedMigration]:
    """Give each migration its position in the migrations sorted by schema path, then by migration name.

    The migrations come in the order of a set, so the sort keeps the positions the same between two runs of a load.
    """
    return [
        PositionedMigration(position=position, migration=migration)
        for position, migration in enumerate(sorted(migrations, key=_migration_sort_key))
    ]


def split_migrations_by_phase(
    migrations: Sequence[PositionedMigration],
) -> tuple[list[PositionedMigration], list[PositionedMigration]]:
    """Split migrations into (kind-update migrations, everything else), preserving relative order.

    Kind-update migrations duplicate node vertices with a new label set. Every other migration
    must only see the duplicated vertices, so the first group has to complete before the second
    group starts.
    """
    kind_update_names = {
        migration_name
        for migration_name, migration_class in MIGRATION_MAP.items()
        if migration_class is NodeKindUpdateMigration
    }
    kind_update_migrations: list[PositionedMigration] = []
    other_migrations: list[PositionedMigration] = []
    for positioned in migrations:
        if positioned.migration.migration_name in kind_update_names:
            kind_update_migrations.append(positioned)
        else:
            other_migrations.append(positioned)
    return kind_update_migrations, other_migrations


async def _migrate_schema_path_at_position(
    position: int,
    recorder: MigrationRecorder,
    branch: Branch,
    migration_name: str,
    schema_path: SchemaPath,
    database: InfrahubDatabase,
    at: Timestamp,
    new_node_schema: MainSchemaTypes | None,
    previous_node_schema: MainSchemaTypes,
    derived_schemas: list[DerivedSchemaPair],
    user_id: str,
) -> PositionedMigrationResult:
    await recorder.migration_started(position=position)
    result = await schema_path_migrate(
        branch=branch,
        migration_name=migration_name,
        schema_path=schema_path,
        database=database,
        at=at,
        new_node_schema=new_node_schema,
        previous_node_schema=previous_node_schema,
        derived_schemas=derived_schemas,
        user_id=user_id,
    )
    return PositionedMigrationResult(position=position, result=result)


async def _apply_migration_batch(
    message: SchemaApplyMigrationData,
    migrations: Sequence[PositionedMigration],
    recorder: MigrationRecorder,
    database: InfrahubDatabase,
    log: logging.Logger | LoggingAdapter,
    max_concurrent_execution: int | None = None,
) -> list[str]:
    if max_concurrent_execution:
        batch = InfrahubBatch(max_concurrent_execution=max_concurrent_execution)
    else:
        batch = InfrahubBatch()
    error_messages: list[str] = []

    if not migrations:
        return error_messages

    for positioned in migrations:
        migration = positioned.migration
        log.info(f"Preparing migration for {migration.migration_name!r} ({migration.routing_key})")

        new_node_schema: MainSchemaTypes | None = None

        if message.new_schema.has(name=migration.path.schema_kind):
            new_node_schema = message.new_schema.get(name=migration.path.schema_kind)

        if new_node_schema and new_node_schema.id:
            previous_node_schema = message.previous_schema.get_by_id(id=new_node_schema.id)
        else:
            previous_node_schema = message.previous_schema.get(name=migration.path.schema_kind)

        if not previous_node_schema:
            raise ValueError(
                f"Unable to find the previous version of the schema for {migration.path.schema_kind}, in order to run the migration."
            )

        batch.add(
            task=_migrate_schema_path_at_position,
            position=positioned.position,
            recorder=recorder,
            branch=message.branch,
            migration_name=migration.migration_name,
            new_node_schema=new_node_schema,
            previous_node_schema=previous_node_schema,
            derived_schemas=get_derived_schema_pairs(
                previous_schema_branch=message.previous_schema,
                new_schema_branch=message.new_schema,
                previous_node_schema=previous_node_schema,
                new_node_schema=new_node_schema,
            ),
            schema_path=migration.path,
            database=database,
            user_id=message.user_id,
            at=message.at,
        )

    async for _, positioned_result in batch.execute():
        await recorder.migration_ended(position=positioned_result.position, result=positioned_result.result)
        error_messages.extend(positioned_result.result.errors)

    return error_messages


@flow(name="schema_apply_migrations", flow_run_name="Apply schema migrations", persist_result=True)
async def schema_apply_migrations(message: SchemaApplyMigrationData) -> list[str]:
    await add_branch_tag(branch_name=message.branch.name)
    log = get_run_logger()

    database = await get_database()

    async with database.start_session() as db:
        recorder = build_migration_recorder(db=db, application_id=message.application_id)
        return await _apply_migrations(message=message, recorder=recorder, database=database, log=log)


async def _apply_migrations(
    message: SchemaApplyMigrationData,
    recorder: MigrationRecorder,
    database: InfrahubDatabase,
    log: logging.Logger | LoggingAdapter,
) -> list[str]:
    error_messages: list[str] = []

    if not message.migrations:
        return error_messages

    positioned_migrations = position_migrations(migrations=message.migrations)
    await recorder.register(migrations=[positioned.migration for positioned in positioned_migrations])

    kind_update_migrations, other_migrations = split_migrations_by_phase(migrations=positioned_migrations)

    # kind-update migrations duplicate node vertices and re-point their edges; two concurrent
    # duplications over overlapping vertices can each create a replacement vertex, so they must
    # run one at a time
    error_messages.extend(
        await _apply_migration_batch(
            message=message,
            migrations=kind_update_migrations,
            recorder=recorder,
            database=database,
            log=log,
            max_concurrent_execution=1,
        )
    )
    if error_messages:
        log.warning("Kind-update migrations reported errors, skipping the remaining migrations")
        return error_messages

    error_messages.extend(
        await _apply_migration_batch(
            message=message, migrations=other_migrations, recorder=recorder, database=database, log=log
        )
    )

    return error_messages


@task(
    name="schema-path-migrate",
    task_run_name="Migrate Schema Path {migration_name} on {branch.name}",
    description="Apply a given migration to the database",
    retries=3,
    cache_policy=NONE,
)
async def schema_path_migrate(
    branch: Branch,
    migration_name: str,
    schema_path: SchemaPath,
    database: InfrahubDatabase,
    at: Timestamp,
    new_node_schema: MainSchemaTypes | None = None,
    previous_node_schema: MainSchemaTypes | None = None,
    derived_schemas: list[DerivedSchemaPair] | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> SchemaMigrationPathResponseData:
    log = get_run_logger()

    async with database.start_session() as db:
        node_kind = None
        if new_node_schema:
            node_kind = new_node_schema.kind
        elif previous_node_schema:
            node_kind = previous_node_schema.kind

        log.info(
            f"Migration for {node_kind} starting {schema_path.get_path()}",
        )
        migration_class = MIGRATION_MAP.get(migration_name)
        if not migration_class:
            raise ValueError(f"Unable to find the migration class for {migration_name}")

        migration = migration_class(  # type: ignore[call-arg]  # ty: ignore[missing-argument]
            new_node_schema=new_node_schema,
            previous_node_schema=previous_node_schema,
            derived_schemas=derived_schemas or [],
            schema_path=schema_path,
        )
        execution_result = await migration.execute(
            migration_input=MigrationInput(db=db, at=at, user_id=user_id), branch=branch
        )

        log.info(f"Migration completed for {migration_name}")
        log.debug(f"execution_result {execution_result}")

        return SchemaMigrationPathResponseData(
            migration_name=migration_name,
            schema_path=schema_path,
            errors=execution_result.errors,
            nbr_migrations_executed=execution_result.nbr_migrations_executed,
        )
