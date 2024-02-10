import importlib
import logging
from asyncio import run as aiorun
from pathlib import Path

import typer
from rich.logging import RichHandler

from infrahub import config
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.graph.migrations import get_migrations
from infrahub.core.initialization import first_time_initialization, get_root_node, initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.database.constants import DatabaseType
from infrahub.log import get_logger

from .transfer.neo4j.backup_runner import Neo4jBackupRunner, Neo4jRestoreRunner

app = typer.Typer()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]


@app.callback()
def callback() -> None:
    """
    Manage the graph in the database.
    """


async def _init() -> None:
    """Erase the content of the database and initialize it with the core schema."""

    log = get_logger()

    # --------------------------------------------------
    # CLEANUP
    #  - For now we delete everything in the database
    #   TODO, if possible try to implement this in an idempotent way
    # --------------------------------------------------

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
    async with dbdriver.start_transaction() as db:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)

    await dbdriver.close()


async def _load_test_data(dataset: str) -> None:
    """Load test data into the database from the test_data directory."""

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


async def _migrate(check: bool) -> None:
    log = get_logger()

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
    async with dbdriver.start_session() as db:
        log.info("Checking current state of the Database")

        root_node = await get_root_node(db=db)
        migrations = await get_migrations(root=root_node)

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
def init(
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
) -> None:
    """Erase the content of the database and initialize it with the core schema."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    aiorun(_init())


@app.command()
def load_test_data(
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    dataset: str = "dataset01",
) -> None:
    """Load test data into the database from the `test_data` directory."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    aiorun(_load_test_data(dataset=dataset))


@app.command()
def migrate(
    check: bool = typer.Option(False, help="Check the state of the database without applying the migrations."),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""

    config.load_and_exit(config_file_name=config_file)

    aiorun(_migrate(check=check))


@app.command()
def backup(
    backup_directory: str = typer.Argument(default="infrahub-backups", help="Where to save the backup files"),
    database_url: str = typer.Option(default=None, help="URL of database, null implies a local database container"),
    database_backup_port: int = typer.Option(
        default=6362, help="Port that the database is listening on for backup commands"
    ),
    aggregate_incremental_backups: bool = typer.Option(
        default=True, help="Combine any existing incremental backups into one full backup per database"
    ),
    quiet: bool = typer.Option(default=False, help="Whether to output status messages to terminal"),
    keep_helper_container: bool = typer.Option(default=False, help="Keep docker container used to run backup"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Export the entire database"""
    config.load_and_exit(config_file_name=config_file)
    backup_path = Path(backup_directory)
    log = logging.getLogger("infrahub")

    if config.SETTINGS.database.db_type == DatabaseType.MEMGRAPH:
        log.error("Database backup is not yet supported for memgraph")
        return
    backup_runner = Neo4jBackupRunner(be_quiet=quiet, keep_helper_container=keep_helper_container)
    backup_runner.backup(backup_path, database_url, database_backup_port, aggregate_incremental_backups)


@app.command()
def restore(
    backup_directory: str = typer.Argument(
        default="infrahub-backups", help="Directory where the backup files are saved"
    ),
    database_cypher_port: int = typer.Option(
        default=7687, help="Port that the Infrahub database container uses for cypher connections"
    ),
    keep_helper_container: bool = typer.Option(default=False, help="Keep docker container used to run backup"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Restore the database"""
    config.load_and_exit(config_file_name=config_file)
    backup_path = Path(backup_directory)
    log = logging.getLogger("infrahub")

    if config.SETTINGS.database.db_type == DatabaseType.MEMGRAPH:
        log.error("Database restore is not yet supported for memgraph")
        return
    backup_runner = Neo4jRestoreRunner(
        keep_helper_container=keep_helper_container, database_cypher_port=database_cypher_port
    )
    backup_runner.restore(backup_path)
