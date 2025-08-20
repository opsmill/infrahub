import asyncio
import logging
import os
import signal
from typing import TYPE_CHECKING, Any

import typer
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.exceptions import Error as SdkError
from prometheus_client import start_http_server
from rich.logging import RichHandler

from infrahub import __version__, config
from infrahub.components import ComponentType
from infrahub.core.initialization import initialization
from infrahub.dependencies.registry import build_component_registry
from infrahub.git import initialize_repositories_directory
from infrahub.lock import initialize_lock
from infrahub.log import get_logger
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.trace import configure_trace

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext

app = AsyncTyper()
log = get_logger()

shutdown_event = asyncio.Event()


def signal_handler(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
    shutdown_event.set()


signal.signal(signal.SIGINT, signal_handler)


@app.callback()
def callback() -> None:
    """
    Control the Git Agent.
    """


async def initialize_git_agent(service: InfrahubServices) -> None:
    service.log.info("Initializing Git Agent ...")
    initialize_repositories_directory()


@app.command()
async def start(
    ctx: typer.Context,
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    port: int = typer.Argument(8000, envvar="INFRAHUB_METRICS_PORT", help="Port used to expose a metrics endpoint"),
) -> None:
    """Start Infrahub Git Agent."""
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("aio_pika").setLevel(logging.ERROR)
    logging.getLogger("aiormq").setLevel(logging.ERROR)
    logging.getLogger("git").setLevel(logging.ERROR)
    logging.getLogger("aiosqlite").setLevel(logging.ERROR)

    log.debug(f"Config file : {config_file}")
    # Prevent git from interactively prompting the user for passwords if the credentials provided
    # by the credential helper is failing.
    os.environ["GIT_TERMINAL_PROMPT"] = "0"

    context: CliContext = ctx.obj

    config.load_and_exit(config_file_name=config_file)

    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(name)s | %(message)s" if debug else "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

    # Start the metrics endpoint
    start_http_server(port)

    # initialize the Infrahub Client and query the list of branches to validate that the API is reacheable and the auth is working
    log.debug(f"Using Infrahub API at {config.SETTINGS.main.internal_address}")
    client = InfrahubClient(
        config=Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True, log=log)
    )
    try:
        await client.branch.all()
    except SdkError as exc:
        log.error(f"Error in communication with Infrahub: {exc.message}")
        raise typer.Exit(1) from None

    # Initialize trace
    if config.SETTINGS.trace.enable:
        configure_trace(
            service="infrahub-git-agent",
            version=__version__,
            exporter_type=config.SETTINGS.trace.exporter_type,
            exporter_endpoint=config.SETTINGS.trace.exporter_endpoint,
            exporter_protocol=config.SETTINGS.trace.exporter_protocol,
        )

    database = await context.init_db(retry=1)

    workflow = config.OVERRIDE.workflow or (
        WorkflowWorkerExecution()
        if config.SETTINGS.workflow.driver == config.WorkflowDriver.WORKER
        else WorkflowLocalExecution()
    )

    component_type = ComponentType.GIT_AGENT
    message_bus = config.OVERRIDE.message_bus or (
        await InfrahubMessageBus.new_from_driver(component_type=component_type, driver=config.SETTINGS.broker.driver)
    )
    cache = config.OVERRIDE.cache or (await InfrahubCache.new_from_driver(driver=config.SETTINGS.cache.driver))

    service = await InfrahubServices.new(
        cache=cache,
        client=client,
        database=database,
        workflow=workflow,
        message_bus=message_bus,
        component_type=component_type,
    )

    # Initialize the lock
    initialize_lock(service=service)

    async with service.database.start_session() as db:
        await initialization(db=db)

    await service.component.refresh_schema_hash()

    await initialize_git_agent(service=service)

    build_component_registry()

    log.info("Initialized Git Agent ...")

    await shutdown_event.wait()

    log.info("Shutdown of Git agent requested")

    await service.shutdown()
    log.info("All services stopped")
