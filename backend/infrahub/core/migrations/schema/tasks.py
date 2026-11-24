from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.runner import SchemaMigrationRunner
from infrahub.core.migrations.schema.scheduler import MigrationScheduler
from infrahub.core.migrations.shared import DerivedSchemaPair, MigrationInput
from infrahub.core.schema.derived_kinds import get_object_template_kind, get_profile_kind
from infrahub.core.schema_change.factory import build_migration_recorder
from infrahub.workers.dependencies import get_database
from infrahub.workflows.utils import add_branch_tag

from .models import SchemaApplyMigrationData, SchemaMigrationPathResponseData

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.path import SchemaPath
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


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


MAX_CONCURRENT_MIGRATION_GROUPS = 5


class TaskSchemaPathMigrator:
    """Apply one migration through the `schema-path-migrate` task."""

    def __init__(self, database: InfrahubDatabase) -> None:
        self.database = database

    async def migrate(
        self, migration: SchemaUpdateMigrationInfo, data: SchemaApplyMigrationData
    ) -> SchemaMigrationPathResponseData:
        new_node_schema: MainSchemaTypes | None = None

        if data.new_schema.has(name=migration.path.schema_kind):
            new_node_schema = data.new_schema.get(name=migration.path.schema_kind)

        if new_node_schema and new_node_schema.id:
            previous_node_schema = data.previous_schema.get_by_id(id=new_node_schema.id)
        else:
            previous_node_schema = data.previous_schema.get(name=migration.path.schema_kind)

        if not previous_node_schema:
            raise ValueError(
                f"Unable to find the previous version of the schema for {migration.path.schema_kind}, in order to run the migration."
            )

        return await schema_path_migrate(
            branch=data.branch,
            migration_name=migration.migration_name,
            new_node_schema=new_node_schema,
            previous_node_schema=previous_node_schema,
            derived_schemas=get_derived_schema_pairs(
                previous_schema_branch=data.previous_schema,
                new_schema_branch=data.new_schema,
                previous_node_schema=previous_node_schema,
                new_node_schema=new_node_schema,
            ),
            schema_path=migration.path,
            database=self.database,
            user_id=data.user_id,
            at=data.at,
        )


@flow(name="schema_apply_migrations", flow_run_name="Apply schema migrations", persist_result=True)
async def schema_apply_migrations(message: SchemaApplyMigrationData) -> list[str]:
    await add_branch_tag(branch_name=message.branch.name)
    log = get_run_logger()

    database = await get_database()

    async with database.start_session() as db:
        runner = SchemaMigrationRunner(
            scheduler=MigrationScheduler(migration_classes=MIGRATION_MAP),
            migrator=TaskSchemaPathMigrator(database=database),
            recorder=build_migration_recorder(db=db, application_id=message.application_id),
            max_concurrent_groups=MAX_CONCURRENT_MIGRATION_GROUPS,
            log=log,
        )
        return await runner.run(data=message)


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
    node_ids: list[str] | None = None,
) -> SchemaMigrationPathResponseData:
    """Run one schema migration on the nodes in `node_ids`, or on every node when it is `None`.

    A caller passes `node_ids` wrapped in `quote()`, because the list grows with the data.

    Raises:
        ValueError: If no migration class is registered under `migration_name`.

    """
    log = get_run_logger()

    async with database.start_session() as db:
        node_kind = None
        if new_node_schema:
            node_kind = new_node_schema.kind
        elif previous_node_schema:
            node_kind = previous_node_schema.kind

        node_scope = f"on {len(node_ids)} nodes" if node_ids is not None else "on all nodes"
        log.info(
            f"Migration for {node_kind} starting {schema_path.get_path()} {node_scope}",
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
            migration_input=MigrationInput(
                db=db,
                at=at,
                user_id=user_id,
                node_ids=frozenset(node_ids) if node_ids is not None else None,
            ),
            branch=branch,
        )

        log.info(f"Migration completed for {migration_name}")
        log.debug(f"execution_result {execution_result}")

        return SchemaMigrationPathResponseData(
            migration_name=migration_name,
            schema_path=schema_path,
            errors=execution_result.errors,
            nbr_migrations_executed=execution_result.nbr_migrations_executed,
        )
