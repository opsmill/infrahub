import importlib
import logging
import os
import subprocess
import sys
from asyncio import run as aiorun
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from infrahub import config
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.graph.migrations import get_migrations
from infrahub.core.initialization import first_time_initialization, get_root_node, initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.database.constants import DatabaseType
from infrahub.log import get_logger

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


def _neo4j_export(export_dir: Path) -> None:
    # pylint: disable=import-outside-toplevel,too-many-statements
    import docker

    neo4j_docker_image = os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:5.16.0-community")
    exporter_container_name = "neo4j-export-helper"
    container_export_dir = "/tmp/neo4jdump"
    console = Console()

    client = docker.from_env()
    console.print("Getting database container")
    database_container = client.containers.list(all=True, filters={"label": "infrahub_role=database"})[0]
    if database_container.status == "running":
        console.print("Stopping database container")
        database_container.stop()
    try:
        existing_exporter_container = client.containers.get(exporter_container_name)
        console.print("Existing export container found, removing")
        existing_exporter_container.stop()
        existing_exporter_container.remove()
    except docker.errors.NotFound:
        pass
    console.print("Starting new export container")
    exporter_container = client.containers.run(
        volumes_from=database_container.name,
        name=exporter_container_name,
        image=neo4j_docker_image,
        tty=True,
        detach=True,
        command="/bin/bash",
    )
    exporter_container.exec_run(["mkdir", container_export_dir])
    console.print("Starting neo4j database export")
    export_command = ["neo4j-admin", "database", "dump", "*", f"--to-path={container_export_dir}"]
    exit_code, response = exporter_container.exec_run(export_command, stdout=True, stderr=True)

    if exit_code != 0:
        console.print("[red]neo4j export command failed")
        console.print(f"    export command: {' '.join(export_command)}")
        console.print("    response:")
        console.print(response.decode())
        console.print("[green]Restarting Infrahub database container")
        database_container.start()
        sys.exit(exit_code)

    console.print("Neo4j database export complete")
    console.print("Transferring files from export container")
    export_dir.mkdir()
    try:
        subprocess.run(
            ["docker", "cps", f"{exporter_container_name}:{container_export_dir}/.", f"{export_dir}"], check=True
        )
    except subprocess.CalledProcessError as exc:
        export_dir.rmdir()
        console.print("[red] failed to copy export files from docker container")
        console.print(f"    failed command: {exc.cmd}")
        if exc.stderr or exc.output:
            console.print(f"    failure details: {exc.stderr or exc.output}")
        console.print("[green]Restarting Infrahub database container")
        database_container.start()
        sys.exit(exc.returncode)

    console.print("Removing export container")
    exporter_container.stop()
    exporter_container.remove()
    console.print("Restarting database container")
    database_container.start()
    console.print(f"Database dump files are in {export_dir.absolute()}")


def _default_export_dir() -> str:
    right_now = datetime.now(timezone.utc).astimezone()
    timestamp = right_now.strftime("%Y%m%d-%H%M%S")
    return f"full-infrahub-export-{timestamp}"


@app.command()
def export(
    export_directory: str = typer.Argument(default=_default_export_dir, help="Where to save export files"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Export the entire database"""
    config.load_and_exit(config_file_name=config_file)
    export_path = Path(export_directory)
    if export_path.exists():
        raise ValueError(f"Export directory {export_path} already exists")

    if config.SETTINGS.database.db_type == DatabaseType.MEMGRAPH:
        ...
    else:
        _neo4j_export(export_path)
