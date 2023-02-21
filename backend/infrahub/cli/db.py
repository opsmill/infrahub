import importlib
import logging
from asyncio import run as aiorun

import typer
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.database import get_db

app = typer.Typer()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]


async def _init(config_file: str):
    """Erase the content of the database and initialize it with the core schema."""
    config.load_and_exit(config_file_name=config_file)

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

    db = await get_db()

    async with db.session(database=config.SETTINGS.database.database) as session:
        log.info("Delete All Nodes")
        await delete_all_nodes(session=session)
        await first_time_initialization(session=session)

    await db.close()


async def _load_test_data(config_file: str, dataset: str):
    """Load test data into the database from the test_data directory."""

    config.load_and_exit(config_file_name=config_file)

    db = await get_db()

    async with db.session(database=config.SETTINGS.database.database) as session:
        await initialization(session=session)

        log_level = "DEBUG"

        FORMAT = "%(message)s"
        logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
        logging.getLogger("infrahub")

        dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
        await dataset_module.load_data(session=session)

    await db.close()


@app.command()
def init(config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):
    """Erase the content of the database and initialize it with the core schema."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    aiorun(_init(config_file=config_file))


@app.command()
def load_test_data(
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"), dataset: str = "dataset01"
):
    """Load test data into the database from the test_data directory."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    aiorun(_load_test_data(config_file=config_file, dataset=dataset))
