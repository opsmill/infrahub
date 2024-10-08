from prefect import flow, task
from prefect.logging import get_run_logger
from prefect.runtime import task_run

from infrahub.core.migrations import MIGRATION_MAP
from infrahub.log import get_logger
from infrahub.message_bus.messages.schema_migration_path import (
    SchemaMigrationPath,
    SchemaMigrationPathData,
    SchemaMigrationPathResponse,
    SchemaMigrationPathResponseData,
)
from infrahub.services import InfrahubServices, services

log = get_logger()


@flow(name="schema-migration-path")
async def path(message: SchemaMigrationPath, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        node_kind = None
        if message.new_node_schema:
            node_kind = message.new_node_schema.kind
        elif message.previous_node_schema:
            node_kind = message.previous_node_schema.kind

        service.log.info(
            "schema.migration.path - received",
            migration=message.migration_name,
            node_kind=node_kind,
            path=message.schema_path.get_path(),
        )
        migration_class = MIGRATION_MAP.get(message.migration_name)
        if not migration_class:
            raise ValueError(f"Unable to find the migration class for {message.migration_name}")

        migration = migration_class(
            new_node_schema=message.new_node_schema,
            previous_node_schema=message.previous_node_schema,
            schema_path=message.schema_path,
        )
        execution_result = await migration.execute(db=db, branch=message.branch)

        service.log.info(
            "schema.migration.path - completed",
            migration=message.migration_name,
            node_kind=node_kind,
            path=message.schema_path.get_path(),
            result=execution_result,
        )
        if message.reply_requested:
            response = SchemaMigrationPathResponse(
                data=SchemaMigrationPathResponseData(
                    migration_name=message.migration_name,
                    schema_path=message.schema_path,
                    errors=execution_result.errors,
                    nbr_migrations_executed=execution_result.nbr_migrations_executed,
                )
            )
            await service.reply(message=response, initiator=message)


def generate_task_name() -> str:
    task_name = task_run.task_name
    message: SchemaMigrationPathData = task_run.parameters["message"]
    return f"{task_name}-{message.branch.name}-{message.migration_name}"


@task(
    task_run_name=generate_task_name,
    description="Apply a given migration to the database",
    retries=3,
)
async def schema_path_migrate(message: SchemaMigrationPathData) -> SchemaMigrationPathResponseData:
    service = services.service
    logger = get_run_logger()

    async with service.database.start_session() as db:
        node_kind = None
        if message.new_node_schema:
            node_kind = message.new_node_schema.kind
        elif message.previous_node_schema:
            node_kind = message.previous_node_schema.kind

        service.log.info(
            "schema.migration.path - received",
            migration=message.migration_name,
            node_kind=node_kind,
            path=message.schema_path.get_path(),
        )
        migration_class = MIGRATION_MAP.get(message.migration_name)
        if not migration_class:
            raise ValueError(f"Unable to find the migration class for {message.migration_name}")

        migration = migration_class(
            new_node_schema=message.new_node_schema,
            previous_node_schema=message.previous_node_schema,
            schema_path=message.schema_path,
        )
        execution_result = await migration.execute(db=db, branch=message.branch)

        logger.info(f"Migration completed for {message.migration_name}")

        service.log.info(
            "schema.migration.path - completed",
            migration=message.migration_name,
            node_kind=node_kind,
            path=message.schema_path.get_path(),
            result=execution_result,
        )

        return SchemaMigrationPathResponseData(
            migration_name=message.migration_name,
            schema_path=message.schema_path,
            errors=execution_result.errors,
            nbr_migrations_executed=execution_result.nbr_migrations_executed,
        )
