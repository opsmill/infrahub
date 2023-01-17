import asyncio
import logging
import signal
import sys
from asyncio import run as aiorun

import typer
from aio_pika import IncomingMessage
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.exceptions import RepositoryError
from infrahub.git import (
    InfrahubRepository,
    handle_git_check_message,
    handle_git_rpc_message,
    handle_git_transform_message,
    initialize_repositories_directory,
)
from infrahub.lock import registry as lock_registry
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import (
    InfrahubMessage,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub_client import InfrahubClient

app = typer.Typer()


def signal_handler(signal, frame):
    print("Git Agent terminated by user.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


# Master
#  Check if a new version of the repo/ branch is available online


# All
#   Listen to Git Request
#    Merge
#    Pull
#    Push
#   Read Repo and look for
#     Schema
#     Data
#     Forms
#     Resource Allocation
#     Validators.          RPC
#     Template.           HTTP
#     Jinja Filters
#     Checks.               RPC ?
#     API Endpoint.    HTTP


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

                        elif rpc.type == MessageType.CHECK:
                            response = await handle_git_check_message(message=rpc, client=client)

                        else:
                            response = InfrahubRPCResponse(status=RPCStatusCode.NOT_FOUND.value)

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

    initialize_repositories_directory()

    # TODO Validate access to the GraphQL API with the proper credentials
    branches = await client.get_list_branches()
    repositories = await client.get_list_repositories(branches=branches)

    for repo_name, repository in repositories.items():
        async with lock_registry.get(repo_name):
            try:
                repo = await InfrahubRepository.init(
                    id=repository.id, name=repository.name, location=repository.location, client=client
                )
            except RepositoryError:
                repo = await InfrahubRepository.new(
                    id=repository.id, name=repository.name, location=repository.location, client=client
                )
                await repo.import_objects_from_files(branch_name=repo.default_branch_name)

            await repo.sync()


async def monitor_remote_activity(client: InfrahubClient, interval: int, log: logging.Logger):
    log.info("Monitoring remote repository for updates .. ")

    while True:
        branches = await client.get_list_branches()
        repositories = await client.get_list_repositories(branches=branches)

        for repo_name, repository in repositories.items():
            async with lock_registry.get(repo_name):
                repo = await InfrahubRepository.init(
                    id=repository.id, name=repository.name, location=repository.location, client=client
                )
                await repo.sync()

        await asyncio.sleep(interval)


async def _start(listen: str, port: int, debug: bool, interval: int, config_file: str):
    """Start Infrahub Git Agent."""

    # Query the list of repo and try to initialize all of them
    # Wait for messages
    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(name)s | %(message)s" if debug else "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub.worker")

    log.debug(f"Config file : {config_file}")

    config.load_and_exit(config_file)

    client = await InfrahubClient.init(address=config.SETTINGS.main.internal_address)

    await initialize_git_agent(client=client, log=log)

    tasks = [
        asyncio.create_task(subscribe_rpcs_queue(client=client, log=log)),
        asyncio.create_task(monitor_remote_activity(client=client, interval=interval, log=log)),
    ]

    await asyncio.gather(*tasks)


@app.command()
def start(
    listen: str = "127.0.0.1",
    port: int = 5672,
    interval: int = 10,
    debug: bool = False,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
):
    # logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("aio_pika").setLevel(logging.ERROR)
    logging.getLogger("aiormq").setLevel(logging.ERROR)
    logging.getLogger("git").setLevel(logging.ERROR)

    aiorun(_start(listen=listen, port=port, interval=interval, debug=debug, config_file=config_file))
