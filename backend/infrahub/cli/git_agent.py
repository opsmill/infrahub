import asyncio
import logging
import signal
import sys
from asyncio import run as aiorun

import typer
from aio_pika import IncomingMessage
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.git import (
    handle_git_rpc_message,
    handle_git_transform_message,
    handle_message,
    initialize_repositories_directory,
)
from infrahub.git.actions import sync_remote_repositories
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import (
    InfrahubMessage,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub_client import InfrahubClient

app = typer.Typer()


def signal_handler(*args, **kwargs):  # pylint: disable=unused-argument
    print("Git Agent terminated by user.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


@app.callback()
def callback():
    """
    Control the Git Agent.
    """


async def subscribe_rpcs_queue(client: InfrahubClient, log: logging.Logger):
    """Subscribe to the RPCs queue and execute the corresponding action when a valid RPC is received."""
    # TODO generate an exception if the broker is not properly configured
    # and return a proper message to the user
    connection = await get_broker()

    # Create a channel and subscribe to the incoming RPC queue
    channel = await connection.channel()
    queue = await channel.declare_queue(f"{config.SETTINGS.broker.namespace}.rpcs")

    log.info("Waiting for RPC instructions to execute .. ")
    async with queue.iterator() as qiterator:
        message: IncomingMessage
        async for message in qiterator:
            try:
                async with message.process(requeue=False):
                    assert message.reply_to is not None

                    try:
                        rpc = InfrahubMessage.convert(message)
                        log.debug(f"Received RPC message {rpc.type}")

                        if rpc.type == MessageType.GIT:
                            response = await handle_git_rpc_message(message=rpc, client=client)

                        elif rpc.type == MessageType.TRANSFORMATION:
                            response = await handle_git_transform_message(message=rpc, client=client)

                        else:
                            response = await handle_message(message=rpc, client=client)

                        log.info(f"RPC Execution Completed {rpc.type} | {rpc.action} | {response.status} ")
                    except Exception as exc:  # pylint: disable=broad-except
                        log.critical(exc, exc_info=True)
                        response = InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR.value, errors=[str(exc)])

                    finally:
                        await response.send(
                            channel=channel, correlation_id=message.correlation_id, reply_to=message.reply_to
                        )

            except Exception:  # pylint: disable=broad-except
                log.exception("Processing error for message %r", message)


async def initialize_git_agent(client: InfrahubClient, log: logging.Logger):
    log.info("Initializing Git Agent ...")
    initialize_repositories_directory()

    # TODO Validate access to the GraphQL API with the proper credentials
    await sync_remote_repositories(client=client)


async def monitor_remote_activity(client: InfrahubClient, interval: int, log: logging.Logger):
    log.info("Monitoring remote repository for updates .. ")

    while True:
        await sync_remote_repositories(client=client)
        await asyncio.sleep(interval)


async def _start(debug: bool, interval: int, config_file: str):
    """Start Infrahub Git Agent."""

    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(name)s | %(message)s" if debug else "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub.git")

    log.debug(f"Config file : {config_file}")

    config.load_and_exit(config_file)

    # initialize the Infrahub Client and query the list of branches to validate that the API is reacheable and the auth is working
    log.debug(f"Using Infrahub API at {config.SETTINGS.main.internal_address}")
    client = await InfrahubClient.init(address=config.SETTINGS.main.internal_address, retry_on_failure=True, log=log)
    await client.branch.all()

    await initialize_git_agent(client=client, log=log)

    tasks = [
        asyncio.create_task(subscribe_rpcs_queue(client=client, log=log)),
        asyncio.create_task(monitor_remote_activity(client=client, interval=interval, log=log)),
    ]

    await asyncio.gather(*tasks)


@app.command()
def start(
    interval: int = 10,
    debug: bool = False,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
):
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("aio_pika").setLevel(logging.ERROR)
    logging.getLogger("aiormq").setLevel(logging.ERROR)
    logging.getLogger("git").setLevel(logging.ERROR)

    aiorun(_start(interval=interval, debug=debug, config_file=config_file))
