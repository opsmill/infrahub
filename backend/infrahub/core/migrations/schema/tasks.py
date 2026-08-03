from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.batch import InfrahubBatch
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.path import SchemaPath  # noqa: TC001
from infrahub.core.timestamp import Timestamp
from infrahub.workers.dependencies import get_database
from infrahub.workflows.utils import add_branch_tag

from .models import SchemaApplyMigrationData, SchemaMigrationPathResponseData

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence

    from prefect.logging.loggers import LoggingAdapter

    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


def split_migrations_by_phase(
    migrations: Sequence[SchemaUpdateMigrationInfo],
) -> tuple[list[SchemaUpdateMigrationInfo], list[SchemaUpdateMigrationInfo]]:
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
    kind_update_migrations: list[SchemaUpdateMigrationInfo] = []
    other_migrations: list[SchemaUpdateMigrationInfo] = []
    for migration in migrations:
        if migration.migration_name in kind_update_names:
            kind_update_migrations.append(migration)
        else:
            other_migrations.append(migration)
    return kind_update_migrations, other_migrations


async def _apply_migration_batch(
    message: SchemaApplyMigrationData,
    migrations: Sequence[SchemaUpdateMigrationInfo],
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

    for migration in migrations:
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
            task=schema_path_migrate,
            branch=message.branch,
            migration_name=migration.migration_name,
            new_node_schema=new_node_schema,
            previous_node_schema=previous_node_schema,
            schema_path=migration.path,
            database=await get_database(),
            user_id=message.user_id,
            at=message.at,
        )

    async for _, result in batch.execute():
        error_messages.extend(result.errors)

    return error_messages


@flow(name="schema_apply_migrations", flow_run_name="Apply schema migrations", persist_result=True)
async def schema_apply_migrations(message: SchemaApplyMigrationData) -> list[str]:
    await add_branch_tag(branch_name=message.branch.name)
    log = get_run_logger()

    error_messages: list[str] = []

    if not message.migrations:
        return error_messages

    kind_update_migrations, other_migrations = split_migrations_by_phase(migrations=message.migrations)

    # kind-update migrations duplicate node vertices and re-point their edges; two concurrent
    # duplications over overlapping vertices can each create a replacement vertex, so they must
    # run one at a time
    error_messages.extend(
        await _apply_migration_batch(
            message=message, migrations=kind_update_migrations, log=log, max_concurrent_execution=1
        )
    )
    if error_messages:
        log.warning("Kind-update migrations reported errors, skipping the remaining migrations")
        return error_messages

    error_messages.extend(await _apply_migration_batch(message=message, migrations=other_migrations, log=log))

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

        migration = migration_class(  # type: ignore[call-arg]
            new_node_schema=new_node_schema,  # type: ignore[arg-type]
            previous_node_schema=previous_node_schema,  # type: ignore[arg-type]
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
