from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.batch import InfrahubBatch
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.path import SchemaPath  # noqa: TC001
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.workflows.utils import add_branch_tag

from .models import SchemaApplyMigrationData, SchemaMigrationPathResponseData

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


@flow(name="schema_apply_migrations", flow_run_name="Apply schema migrations", persist_result=True)
async def schema_apply_migrations(message: SchemaApplyMigrationData, service: InfrahubServices) -> list[str]:
    await add_branch_tag(branch_name=message.branch.name)
    log = get_run_logger()

    batch = InfrahubBatch()
    error_messages: list[str] = []

    if not message.migrations:
        return error_messages

    for migration in message.migrations:
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
            service=service,
        )

    async for _, result in batch.execute():
        error_messages.extend(result.errors)

    return error_messages


@task(  # type: ignore[arg-type]
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
    service: InfrahubServices,
    new_node_schema: MainSchemaTypes | None = None,
    previous_node_schema: MainSchemaTypes | None = None,
) -> SchemaMigrationPathResponseData:
    log = get_run_logger()

    async with service.database.start_session() as db:
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
        execution_result = await migration.execute(db=db, branch=branch)

        log.info(f"Migration completed for {migration_name}")
        log.debug(f"execution_result {execution_result}")

        return SchemaMigrationPathResponseData(
            migration_name=migration_name,
            schema_path=schema_path,
            errors=execution_result.errors,
            nbr_migrations_executed=execution_result.nbr_migrations_executed,
        )
