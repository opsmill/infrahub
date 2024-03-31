from pathlib import Path

import typer
from infrahub_sdk.async_typer import AsyncTyper
from rich.progress import (
    Progress,
)

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabaseMode, get_db
from infrahub.database.analyzer import InfrahubDatabaseAnalyzer, query_stats
from infrahub.lock import initialize_lock
from infrahub.log import get_logger
from infrahub.test_data.gen_connected_nodes import GenerateConnectedNodes
from infrahub.test_data.gen_isolated_node import GenerateIsolatedNodes

app = AsyncTyper()

log = get_logger()


@app.command()
async def isolated_node(
    test_name: str = "isolated_node",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    log.info("Starting initialization .. ")
    initialize_lock()
    await initialization(db=db)

    default_branch = await registry.get_branch(db=db)
    tag_schema = registry.schema.get_node_schema(name=InfrahubKind.TAG, branch=default_branch)

    query_stats.name = test_name
    query_stats.measure_memory_usage = True
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    log.info("Start loading data .. ")
    with Progress() as progress:
        loader = GenerateIsolatedNodes(db=db, progress=progress, concurrent_execution=parallel)
        loader.add_callback(callback_name="query_50_tag", task=NodeManager.query, limit=50, schema=tag_schema)
        await loader.load_data(nbr_tags=count, nbr_repository=count)

    query_stats.create_graphs()


@app.command()
async def connected_nodes(
    test_name: str = "connected_nodes",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    log.info("Starting initialization .. ")
    initialize_lock()
    await initialization(db=db)

    default_branch = await registry.get_branch(db=db)
    tag_schema = registry.schema.get_node_schema(name=InfrahubKind.TAG, branch=default_branch)

    query_stats.name = test_name
    query_stats.measure_memory_usage = True
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    log.info("Start loading data .. ")
    with Progress() as progress:
        loader = GenerateConnectedNodes(db=db, progress=progress, concurrent_execution=parallel)
        loader.add_callback(callback_name="query_50_tag", task=NodeManager.query, limit=50, schema=tag_schema)
        await loader.load_data(nbr_tags=count, nbr_repository=count)

    query_stats.create_graphs()


if __name__ == "__main__":
    app()
