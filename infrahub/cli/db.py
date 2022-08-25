import importlib
import logging

import typer
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.utils import delete_all_nodes

app = typer.Typer()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]


@app.command()
def init(config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):

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
    log.info("Delete All Nodes")
    delete_all_nodes()

    first_time_initialization()


@app.command()
def load_test_data(
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"), dataset: str = "dataset01"
):

    config.load_and_exit(config_file_name=config_file)
    initialization()

    log_level = "DEBUG"

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub")

    dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
    dataset_module.load_data()
