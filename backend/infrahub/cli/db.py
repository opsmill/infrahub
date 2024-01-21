import importlib
import logging
from asyncio import run as aiorun

import typer
from rich.console import Console
from rich.logging import RichHandler

from infrahub import config
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.graph.migrations import get_migrations
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.root import Root
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.exceptions import DatabaseError

app = typer.Typer()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]

console = Console()


@app.callback()
def callback() -> None:
    """
    Manage the graph in the database.
    """


async def _init() -> None:
    """Erase the content of the database and initialize it with the core schema."""

    # log_level = "DEBUG" if debug else "INFO"

    log_level = "DEBUG"

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub")

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
        logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console)])
        logging.getLogger("infrahub")

        dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
        await dataset_module.load_data(db=db)

    await dbdriver.close()


async def _migrate(check: bool, debug: bool) -> None:
    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler(console=console)])
    log = logging.getLogger("infrahub")

    dbdriver = InfrahubDatabase(driver=await get_db(retry=1))
    async with dbdriver.start_session() as db:
        log.info("Checking current state of the Database")
        roots = await Root.get_list(db=db)
        if len(roots) == 0:
            await first_time_initialization(db=db)
            roots = await Root.get_list(db=db)

        if len(roots) > 1:
            raise DatabaseError("Database is corrupted, more than 1 root node found.")

        root_node = roots[0]
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
    debug: bool = typer.Option(False, help="Enable verbose logging."),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""

    config.load_and_exit(config_file_name=config_file)

    aiorun(_migrate(check=check, debug=debug))
