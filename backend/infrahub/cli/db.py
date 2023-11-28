import importlib
import logging
from asyncio import run as aiorun

import typer
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db

app = typer.Typer()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]


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

    await db.close()


async def _load_test_data(dataset: str) -> None:
    """Load test data into the database from the test_data directory."""

    db = InfrahubDatabase(driver=await get_db(retry=1))
    async with db.start_session() as db:
        await initialization(db=db)

        log_level = "DEBUG"

        FORMAT = "%(message)s"
        logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
        logging.getLogger("infrahub")

        dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
        await dataset_module.load_data(db=db)

    await db.close()


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
