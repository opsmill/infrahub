from __future__ import annotations

import importlib
import logging
import os
from enum import Enum
from typing import TYPE_CHECKING, Optional

import typer
from infrahub_sdk.async_typer import AsyncTyper
from prefect.testing.utilities import prefect_test_harness
from rich import print as rprint
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.graph.constraints import ConstraintManagerBase, ConstraintManagerMemgraph, ConstraintManagerNeo4j
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.core.initialization import (
    create_anonymous_role,
    create_default_menu,
    create_default_roles,
    create_super_administrator_role,
    create_super_administrators_group,
    first_time_initialization,
    get_root_node,
    initialization,
    initialize_registry,
)
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph import get_graph_migrations
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.database import DatabaseType
from infrahub.log import get_logger
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.local import BusSimulator
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import SCHEMA_APPLY_MIGRATION, SCHEMA_VALIDATE_MIGRATION

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext
    from infrahub.database import InfrahubDatabase

app = AsyncTyper()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]


class ConstraintAction(str, Enum):
    SHOW = "show"
    ADD = "add"
    DROP = "drop"


class IndexAction(str, Enum):
    SHOW = "show"
    ADD = "add"
    DROP = "drop"


@app.callback()
def callback() -> None:
    """
    Manage the graph in the database.
    """


@app.command()
async def init(
    ctx: typer.Context,
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
) -> None:
    """Erase the content of the database and initialize it with the core schema."""

    log = get_logger()

    # --------------------------------------------------
    # CLEANUP
    #  - For now we delete everything in the database
    #   TODO, if possible try to implement this in an idempotent way
    # --------------------------------------------------

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.get_db(retry=1)
    async with dbdriver.start_transaction() as db:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)

    await dbdriver.close()


@app.command()
async def load_test_data(
    ctx: typer.Context,
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    dataset: str = "dataset01",
) -> None:
    """Load test data into the database from the `test_data` directory."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.get_db(retry=1)
    async with dbdriver.start_session() as db:
        await initialization(db=db)

        log_level = "DEBUG"

        FORMAT = "%(message)s"
        logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
        logging.getLogger("infrahub")

        dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
        await dataset_module.load_data(db=db)

    await dbdriver.close()


@app.command()
async def migrate(
    ctx: typer.Context,
    check: bool = typer.Option(False, help="Check the state of the database without applying the migrations."),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""
    log = get_logger()

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.get_db(retry=1)
    async with dbdriver.start_session() as db:
        rprint("Checking current state of the Database")

        await initialize_registry(db=db)
        root_node = await get_root_node(db=db)
        migrations = await get_graph_migrations(root=root_node)

        if not migrations:
            rprint(f"Database up-to-date (v{root_node.graph_version}), no migration to execute.")
        else:
            rprint(
                f"Database needs to be updated (v{root_node.graph_version} -> v{GRAPH_VERSION}), {len(migrations)} migrations pending"
            )

        if migrations and not check:
            for migration in migrations:
                log.debug(f"Execute Migration: {migration.name}")
                execution_result = await migration.execute(db=db)
                validation_result = None

                if execution_result.success:
                    validation_result = await migration.validate_migration(db=db)
                    if validation_result.success:
                        rprint(f"Migration: {migration.name} [green]SUCCESS[/green]")
                        root_node.graph_version = migration.minimum_version + 1
                        await root_node.save(db=db)

                if not execution_result.success or validation_result and not validation_result.success:
                    rprint(f"Migration: {migration.name} [bold red]FAILED[/bold red]")
                    for error in execution_result.errors:
                        rprint(f"  {error}")
                    if validation_result and not validation_result.success:
                        for error in validation_result.errors:
                            rprint(f"  {error}")
                    break

    await dbdriver.close()


@app.command()
async def update_core_schema(  # pylint: disable=too-many-statements
    ctx: typer.Context,
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)
    os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "false"

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.get_db(retry=1)

    error_badge = "[bold red]ERROR[/bold red]"

    async with dbdriver.start_session() as db:
        with prefect_test_harness():
            # ----------------------------------------------------------
            # Initialize Schema and Registry
            # ----------------------------------------------------------
            service = InfrahubServices(
                database=db, message_bus=BusSimulator(database=db), workflow=WorkflowLocalExecution()
            )
            await initialize_registry(db=db)

            default_branch = registry.get_branch_from_registry(branch=registry.default_branch)

            registry.schema = SchemaManager()
            schema = SchemaRoot(**internal_schema)
            registry.schema.register_schema(schema=schema)

            # ----------------------------------------------------------
            # Load Current Schema from the database
            # ----------------------------------------------------------
            schema_default_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
            registry.schema.set_schema_branch(name=default_branch.name, schema=schema_default_branch)
            branch_schema = registry.schema.get_schema_branch(name=registry.default_branch)

            candidate_schema = branch_schema.duplicate()
            candidate_schema.load_schema(schema=SchemaRoot(**internal_schema))
            candidate_schema.load_schema(schema=SchemaRoot(**core_models))
            candidate_schema.load_schema(schema=SchemaRoot(**deprecated_models))
            candidate_schema.process()

            result = branch_schema.validate_update(other=candidate_schema, enforce_update_support=False)
            if result.errors:
                rprint(f"{error_badge} | Unable to update the schema, due to failed validations")
                for error in result.errors:
                    rprint(error.to_string())
                raise typer.Exit(1)

            if not result.diff.all:
                await create_defaults(db=db)
                rprint("Core Schema Up to date, nothing to update")
                raise typer.Exit(0)

            rprint("Core Schema has diff, will need to be updated")
            if debug:
                result.diff.print()

            # ----------------------------------------------------------
            # Validate if the new schema is valid with the content of the database
            # ----------------------------------------------------------
            validate_migration_data = SchemaValidateMigrationData(
                branch=default_branch,
                schema_branch=candidate_schema,
                constraints=result.constraints,
            )
            error_messages = await service.workflow.execute_workflow(
                workflow=SCHEMA_VALIDATE_MIGRATION,
                expected_return=list[str],
                parameters={"message": validate_migration_data},
            )
            if error_messages:
                rprint(f"{error_badge} | Unable to update the schema, due to failed validations")
                for message in error_messages:
                    rprint(message)
                raise typer.Exit(1)

            # ----------------------------------------------------------
            # Update the schema
            # ----------------------------------------------------------
            origin_schema = branch_schema.duplicate()

            # Update the internal schema
            schema_default_branch.load_schema(schema=SchemaRoot(**internal_schema))
            schema_default_branch.process()
            registry.schema.set_schema_branch(name=default_branch.name, schema=schema_default_branch)

            async with db.start_transaction() as dbt:
                await registry.schema.update_schema_branch(
                    schema=candidate_schema,
                    db=dbt,
                    branch=default_branch.name,
                    diff=result.diff,
                    limit=result.diff.all,
                    update_db=True,
                )
                default_branch.update_schema_hash()
                rprint("The Core Schema has been updated")
                if debug:
                    rprint(f"New schema hash: {default_branch.active_schema_hash.main}")
                await default_branch.save(db=dbt)

            # ----------------------------------------------------------
            # Run the migrations
            # ----------------------------------------------------------
            apply_migration_data = SchemaApplyMigrationData(
                branch=default_branch,
                new_schema=candidate_schema,
                previous_schema=origin_schema,
                migrations=result.migrations,
            )
            migration_error_msgs = await service.workflow.execute_workflow(
                workflow=SCHEMA_APPLY_MIGRATION,
                expected_return=list[str],
                parameters={"message": apply_migration_data},
            )

            if migration_error_msgs:
                rprint(f"{error_badge} | Some error(s) happened while running the schema migrations")
                for message in migration_error_msgs:
                    rprint(message)
                raise typer.Exit(1)

            await create_defaults(db=db)


@app.command()
async def constraint(
    ctx: typer.Context,
    action: ConstraintAction = typer.Argument(ConstraintAction.SHOW),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Manage Database Constraints"""
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.get_db(retry=1)

    manager: Optional[ConstraintManagerBase] = None
    if dbdriver.db_type == DatabaseType.NEO4J:
        manager = ConstraintManagerNeo4j.from_graph_schema(db=dbdriver, schema=GRAPH_SCHEMA)
    elif dbdriver.db_type == DatabaseType.MEMGRAPH:
        manager = ConstraintManagerMemgraph.from_graph_schema(db=dbdriver, schema=GRAPH_SCHEMA)
    else:
        print(f"Database type not supported : {dbdriver.db_type}")
        raise typer.Exit(1)

    if action == ConstraintAction.ADD:
        await manager.add()
    elif action == ConstraintAction.DROP:
        await manager.drop()

    constraints = await manager.list()

    console = Console()

    table = Table(title="Database Constraints")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Label")
    table.add_column("Property")

    for item in constraints:
        table.add_row(item.item_name, item.item_label, item.property)

    console.print(table)

    await dbdriver.close()


@app.command()
async def index(
    ctx: typer.Context,
    action: IndexAction = typer.Argument(IndexAction.SHOW),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Manage Database Indexes"""
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.get_db(retry=1)
    dbdriver.manager.index.init(nodes=node_indexes, rels=rel_indexes)

    if action == IndexAction.ADD:
        await dbdriver.manager.index.add()
    elif action == IndexAction.DROP:
        await dbdriver.manager.index.drop()

    indexes = await dbdriver.manager.index.list()

    console = Console()

    table = Table(title="Database Indexes")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Label")
    table.add_column("Property")
    table.add_column("Type")
    table.add_column("Entity Type")

    for item in indexes:
        table.add_row(
            item.name, item.label, ", ".join(item.properties), item.type.value.upper(), item.entity_type.value.upper()
        )

    console.print(table)

    await dbdriver.close()


async def create_defaults(db: InfrahubDatabase) -> None:
    """Create and assign default objects."""
    existing_permissions = await NodeManager.query(
        schema=InfrahubKind.OBJECTPERMISSION,
        db=db,
        limit=1,
    )
    if not existing_permissions:
        await setup_permissions(db=db)

    existing_menu_items = await NodeManager.query(
        schema=InfrahubKind.MENUITEM,
        db=db,
        limit=1,
    )
    if not existing_menu_items:
        await create_default_menu(db=db)


async def setup_permissions(db: InfrahubDatabase) -> None:
    existing_accounts = await NodeManager.query(
        schema=InfrahubKind.ACCOUNT,
        db=db,
        limit=1,
    )
    administrator_role = await create_super_administrator_role(db=db)
    await create_super_administrators_group(db=db, role=administrator_role, admin_accounts=existing_accounts)

    await create_default_roles(db=db)

    if config.SETTINGS.main.allow_anonymous_access:
        await create_anonymous_role(db=db)
