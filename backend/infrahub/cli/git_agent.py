import asyncio
import logging
import signal
import sys
from asyncio import run as aiorun
from typing import Any

import typer
from infrahub_sdk import InfrahubClient
from prometheus_client import start_http_server
from rich.logging import RichHandler

from infrahub import config
from infrahub.components import ComponentType
from infrahub.core.initialization import initialization
from infrahub.database import InfrahubDatabase, get_db
from infrahub.git import initialize_repositories_directory
from infrahub.git.actions import sync_remote_repositories
from infrahub.lock import initialize_lock
from infrahub.log import clear_log_context, get_logger
from infrahub.message_bus import get_broker, messages
from infrahub.message_bus.operations import execute_message
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus

app = typer.Typer()

log = get_logger()


def signal_handler(*args: Any, **kwargs: Any) -> None:  # pylint: disable=unused-argument
    print("Git Agent terminated by user.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


@app.callback()
def callback() -> None:
    """
    Control the Git Agent.
    """


async def subscribe_rpcs_queue(service: InfrahubServices) -> None:
    """Subscribe to the RPCs queue and execute the corresponding action when a valid RPC is received."""
    # TODO generate an exception if the broker is not properly configured
    # and return a proper message to the user
    connection = await get_broker()

    # Create a channel and subscribe to the incoming RPC queue
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.get_queue(f"{config.SETTINGS.broker.namespace}.rpcs")
    log.info("Waiting for RPC instructions to execute .. ")
    async with queue.iterator() as qiterator:
        async for message in qiterator:
            try:
                async with message.process(requeue=False):
                    clear_log_context()
                    if message.routing_key in messages.MESSAGE_MAP:
                        await execute_message(
                            routing_key=message.routing_key, message_body=message.body, service=service
                        )
                    else:
                        log.error(
                            "Unhandled routing key for message", routing_key=message.routing_key, message=message.body
                        )

            except Exception:  # pylint: disable=broad-except
                log.exception("Processing error for message %r" % message)


async def initialize_git_agent(service: InfrahubServices) -> None:
    log.info("Initializing Git Agent ...")
    initialize_repositories_directory()

    # TODO Validate access to the GraphQL API with the proper credentials
    await sync_remote_repositories(service=service)


async def _start(debug: bool, port: int) -> None:
    """Start Infrahub Git Agent."""

    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(name)s | %(message)s" if debug else "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

    # Start the metrics endpoint
    start_http_server(port)

    # initialize the Infrahub Client and query the list of branches to validate that the API is reacheable and the auth is working
    log.debug(f"Using Infrahub API at {config.SETTINGS.main.internal_address}")
    client = await InfrahubClient.init(address=config.SETTINGS.main.internal_address, retry_on_failure=True, log=log)
    await client.branch.all()

    # Initialize the lock
    initialize_lock()

    driver = await get_db()
    database = InfrahubDatabase(driver=driver)
    service = InfrahubServices(
        cache=RedisCache(),
        client=client,
        database=database,
        message_bus=RabbitMQMessageBus(),
        component_type=ComponentType.GIT_AGENT,
    )
    await service.initialize()
    await initialize_git_agent(service=service)

    async with service.database.start_session() as db:
        await initialization(db=db)

    tasks = [
        asyncio.create_task(subscribe_rpcs_queue(service=service)),
    ]

    await asyncio.gather(*tasks)


@app.command()
def start(
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

    log.debug(f"Config file : {config_file}")

    config.load_and_exit(config_file_name=config_file)

    aiorun(_start(debug=debug, port=port))
