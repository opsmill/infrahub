import asyncio
import logging
import signal
import sys
from asyncio import run as aiorun
from typing import TYPE_CHECKING

import typer
from prometheus_client import start_http_server
from rich.logging import RichHandler

from infrahub import config
from infrahub.core.initialization import initialization
from infrahub.database import get_db
from infrahub.git import handle_message, initialize_repositories_directory
from infrahub.git.actions import sync_remote_repositories
from infrahub.lock import initialize_lock
from infrahub.log import clear_log_context, get_logger, set_log_data
from infrahub.message_bus import get_broker, messages
from infrahub.message_bus.events import (
    InfrahubMessage,
    InfrahubRPCResponse,
    RPCStatusCode,
)
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.worker import WorkerCallback
from infrahub.services import InfrahubServices
from infrahub.services.adapters.database.graph_database import GraphDatabase
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus
from infrahub.worker import WORKER_IDENTITY
from infrahub_client import InfrahubClient

if TYPE_CHECKING:
    from aio_pika import IncomingMessage


app = typer.Typer()

log = get_logger()


def signal_handler(*args, **kwargs):  # pylint: disable=unused-argument
    print("Git Agent terminated by user.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


@app.callback()
def callback():
    """
    Control the Git Agent.
    """


async def subscribe_rpcs_queue(client: InfrahubClient):
    """Subscribe to the RPCs queue and execute the corresponding action when a valid RPC is received."""
    # TODO generate an exception if the broker is not properly configured
    # and return a proper message to the user
    connection = await get_broker()

    # Create a channel and subscribe to the incoming RPC queue
    channel = await connection.channel()
    queue = await channel.declare_queue(
        f"{config.SETTINGS.broker.namespace}.rpcs", durable=True, arguments={"x-queue-type": "quorum"}
    )
    events_queue = await channel.declare_queue(name=f"worker-events-{WORKER_IDENTITY}", exclusive=True)

    exchange = await channel.declare_exchange(f"{config.SETTINGS.broker.namespace}.events", type="topic", durable=True)
    await events_queue.bind(exchange, routing_key="refresh.registry.*")

    driver = await get_db()
    database = GraphDatabase(driver=driver)
    service = InfrahubServices(
        client=client, database=database, message_bus=RabbitMQMessageBus(channel=channel, exchange=exchange)
    )
    async with service.database.session as session:
        await initialization(session=session)

    worker_callback = WorkerCallback(service=service)
    await events_queue.consume(worker_callback.run_command, no_ack=True)
    log.info("Waiting for RPC instructions to execute .. ")
    async with queue.iterator() as qiterator:
        message: IncomingMessage
        async for message in qiterator:
            try:
                async with message.process(requeue=False):
                    clear_log_context()
                    if message.routing_key in messages.MESSAGE_MAP:
                        await execute_message(
                            routing_key=message.routing_key, message_body=message.body, service=service
                        )
                        continue
                    assert message.reply_to is not None

                    try:
                        rpc = InfrahubMessage.convert(message)
                        if rpc.request_id:
                            set_log_data(key="request_id", value=rpc.request_id)
                        log.debug("received_message", message_type=rpc.type)
                        response = await handle_message(message=rpc, client=client)

                        log.info(
                            "RPC Execution Completed", message_type=rpc.type, action=rpc.action, status=response.status
                        )
                    except Exception as exc:  # pylint: disable=broad-except
                        log.critical(exc, exc_info=True)
                        response = InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[str(exc)])

                    finally:
                        await response.send(
                            channel=channel, correlation_id=message.correlation_id, reply_to=message.reply_to
                        )

            except Exception:  # pylint: disable=broad-except
                log.exception("Processing error for message %r" % message)


async def initialize_git_agent(client: InfrahubClient):
    log.info("Initializing Git Agent ...")
    initialize_repositories_directory()

    # TODO Validate access to the GraphQL API with the proper credentials
    await sync_remote_repositories(client=client)


async def monitor_remote_activity(client: InfrahubClient, interval: int):
    log.info("Monitoring remote repository for updates .. ")

    while True:
        await sync_remote_repositories(client=client)
        await asyncio.sleep(interval)


async def _start(debug: bool, interval: int, port: int):
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

    await initialize_git_agent(client=client)

    tasks = [
        asyncio.create_task(subscribe_rpcs_queue(client=client)),
        asyncio.create_task(monitor_remote_activity(client=client, interval=interval)),
    ]

    await asyncio.gather(*tasks)


@app.command()
def start(
    interval: int = typer.Option(10, help="Interval in sec between remote repositories update."),
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    port: int = typer.Argument(8000, envvar="INFRAHUB_METRICS_PORT", help="Port used to expose a metrics endpoint"),
):
    """Start Infrahub Git Agent."""
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("aio_pika").setLevel(logging.ERROR)
    logging.getLogger("aiormq").setLevel(logging.ERROR)
    logging.getLogger("git").setLevel(logging.ERROR)

    log.debug(f"Config file : {config_file}")

    config.load_and_exit(config_file_name=config_file)

    aiorun(_start(interval=interval, debug=debug, port=port))
