import importlib
import logging
from enum import Enum
from typing import Optional

import typer
from infrahub_sdk.async_typer import AsyncTyper
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from infrahub import config
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.graph.constraints import ConstraintManagerBase, ConstraintManagerMemgraph, ConstraintManagerNeo4j
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.core.initialization import first_time_initialization, get_root_node, initialization
from infrahub.core.migrations.graph import get_graph_migrations
from infrahub.core.utils import delete_all_nodes
from infrahub.database import DatabaseType, InfrahubDatabase, get_db
from infrahub.log import get_logger

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

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
    async with dbdriver.start_transaction() as db:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)

    await dbdriver.close()


@app.command()
async def load_test_data(
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    dataset: str = "dataset01",
) -> None:
    """Load test data into the database from the `test_data` directory."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
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
    check: bool = typer.Option(False, help="Check the state of the database without applying the migrations."),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""
    log = get_logger()

    config.load_and_exit(config_file_name=config_file)

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
    async with dbdriver.start_session() as db:
        log.info("Checking current state of the Database")

        root_node = await get_root_node(db=db)
        migrations = await get_graph_migrations(root=root_node)

        if not migrations:
            log.info(f"Database up-to-date (v{root_node.graph_version}), no migration to execute.")
        else:
            log.info(
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
                        log.info(f"Migration: {migration.name} SUCCESS")

                if not execution_result.success or validation_result and not validation_result.success:
                    log.info(f"Migration: {migration.name} FAILED")
                    for error in execution_result.errors:
                        log.warning(f"  {error}")
                    if validation_result and not validation_result.success:
                        for error in validation_result.errors:
                            log.warning(f"  {error}")
                    break

    await dbdriver.close()


@app.command()
async def constraint(
    action: ConstraintAction = typer.Argument(ConstraintAction.SHOW),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Manage Database Constraints"""
    config.load_and_exit(config_file_name=config_file)

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))

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
    action: IndexAction = typer.Argument(IndexAction.SHOW),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Manage Database Indexes"""
    config.load_and_exit(config_file_name=config_file)

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
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
