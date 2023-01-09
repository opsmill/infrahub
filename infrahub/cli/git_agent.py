import sys
import logging
import signal
import asyncio
from asyncio import run as aiorun
from typing import List, Dict

import typer
from aio_pika import IncomingMessage
from rich.logging import RichHandler

from infrahub_client import InfrahubClient

import infrahub.config as config
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import (
    get_event_exchange,
    MessageType,
    InfrahubMessage,
    InfrahubRPCResponse,
    RPCStatusCode,
)
from infrahub.exceptions import RepositoryError
from infrahub.git import (
    InfrahubRepository,
    handle_git_rpc_message,
    initialize_repositories_directory,
    get_repositories_directory,
)
from infrahub.lock import registry as lock_registry

app = typer.Typer()

# logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("aio_pika").setLevel(logging.ERROR)
logging.getLogger("aiormq").setLevel(logging.ERROR)
logging.getLogger("git").setLevel(logging.ERROR)


def signal_handler(signal, frame):
    print("\Git Agent terminated by user.")
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

                        else:
                            response = InfrahubRPCResponse(status=RPCStatusCode.NOT_FOUND.value)

                        log.info(f"RPC Execution Completed {rpc.type} | {rpc.action} | {response.status} ")
                    except Exception as exc:
                        response = InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR.value, errors=[str(exc)])

                    finally:
                        await response.send(
                            channel=channel, correlation_id=message.correlation_id, reply_to=message.reply_to
                        )

            except Exception:
                log.exception("Processing error for message %r", message)


async def initialize_git_agent(client: InfrahubClient, log: logging.Logger):

    repos_dir = get_repositories_directory()
    initialize_repositories_directory()

    # TODO Validate access to the GraphQL API with the proper credentials
    branches = await client.get_list_branches()
    repositories = await client.get_list_repositories(branches=branches)

    for repo_name, repository in repositories.items():
        async with lock_registry.get(repo_name):
            try:
                repo = await InfrahubRepository.init(
                    id=repository.id, name=repository.name, location=repository.location
                )
            except RepositoryError as exc:
                repo = await InfrahubRepository.new(
                    id=repository.id, name=repository.name, location=repository.location
                )

            await repo.sync()

            # # Identify the branches that are missing locally and add them
            # local_branches = repo.get_branches_from_local()
            # missing_branches_locally = set(repository.branches.keys()) - set(local_branches.keys())

            # # TODO we need to check if the commit are matching between the database and the value we have on disk
            # for branch_name in missing_branches_locally:
            #     if branch_name in branches and not branches[branch_name].is_data_only:
            #         repo.create_branch_in_git(push_origin=True)


async def monitor_remote_activity(client: InfrahubClient, interval: int, log: logging.Logger):
    log.info("Monitoring remote repository for updates .. ")

    while True:

        # # ----------------------------------------------------------------------
        # # Check all repos on the main branch
        # # -----------------------------------------------------------------------
        # main_branch = Branch.get_by_name(config.SETTINGS.main.default_branch)
        # branches = Branch.get_list()
        # db_branche_names = [item.name for item in branches]

        # for repo in NodeManager.query("Repository", branch=main_branch):

        #     log.debug(f"{repo.name.value} in branch {main_branch.name}")

        #     repo.ensure_exists_locally()

        #     git_repo = repo.get_git_repo_main()

        #     # Pull the latest update from the remote repo
        #     git_repo.remotes.origin.fetch()
        #     git_repo.remotes.origin.pull()
        #     if str(git_repo.head.commit) != str(repo.commit.value):
        #         log.info(
        #             f"{repo.name.value}: Commit on branch {repo._branch.name} ({repo.commit.value}) do not match the local value ({git_repo.head.commit})"
        #         )

        #         repo.commit.value = str(git_repo.head.commit)
        #         repo.save()

        #     # Remove stale branches from the remote repo
        #     for stale_branch in git_repo.remotes.origin.stale_refs:
        #         if not isinstance(stale_branch, git.refs.remote.RemoteReference):
        #             continue

        #         log.debug(f"{repo.name.value}: Cleaning branch {stale_branch.name} no longer present on remote.")
        #         type(stale_branch).delete(git_repo, stale_branch)

        #     # Got over all branches in the remote and check if they already exist locally
        #     # If not, create a new branch locally in the database and in Git and track the remote branch
        #     for remote_branch in git_repo.remotes.origin.refs:
        #         if not isinstance(remote_branch, git.refs.remote.RemoteReference):
        #             continue
        #         short_name = remote_branch.name.replace("origin/", "")

        #         if short_name == "HEAD" or short_name in db_branche_names:
        #             continue

        #         log.info(f"{repo.name.value}: Found new branch {short_name}")

        #         # Create the new branch in the database
        #         # Don't do more for now because we'll process all other repos in the next section
        #         new_branch = Branch(name=short_name, description=f"Created from Repository: {repo.name.value}")
        #         new_branch.save()

        #         # Create the new Branch locally in Git too
        #         local_branch_names = [br.name for br in git_repo.refs if not br.is_remote()]
        #         if short_name not in local_branch_names:
        #             git_repo.git.branch(short_name)

        #     # IMPORT DATA FROM REPOSITORY / BRANCH
        #     import_all_graphql_query(log=log, repo=repo, branch=main_branch, search_directory=repo.directory_default)

        #     import_all_yaml_files(log=log, repo=repo, branch=main_branch, search_directory=repo.directory_default)

        #     # TODO - CLEANUP
        #     #  * CHECK if all worktree match with existing branches
        #     #  * Find a way to match worktree based on commit to clean them as well

        # for branch in Branch.get_list():
        #     if branch.name == config.SETTINGS.main.default_branch:
        #         continue

        #     if branch.is_data_only:
        #         continue

        #     for repo in NodeManager.query("Repository", branch=branch):

        #         # Check if the repository for the branch exist locally
        #         log.debug(f"{repo.name.value} in branch {branch.name}")

        #         if not os.path.isdir(repo.directory_branch):
        #             main_repo = Repo(repo.directory_default)

        #             local_branch_names = [br.name for br in main_repo.refs if not br.is_remote()]
        #             if branch.name not in local_branch_names:
        #                 main_repo.git.branch(branch.name)

        #             # TODO we probably need to check the worktree too at some point
        #             main_repo.git.worktree("add", repo.directory_branch, branch.name)

        #         git_repo = Repo(repo.directory_branch)

        #         # Check if the worktree has been configure to track a specific branch
        #         if not git_repo.active_branch.tracking_branch():
        #             remote_branch = [br for br in git_repo.remotes.origin.refs if br.name == f"origin/{branch.name}"]
        #             if remote_branch:
        #                 git_repo.head.reference.set_tracking_branch(remote_branch[0])
        #                 git_repo.remotes.origin.pull()
        #         else:
        #             git_repo.remotes.origin.pull()

        #         if str(git_repo.head.commit) != str(repo.commit.value):
        #             log.info(
        #                 f"{repo.name.value}: Commit on branch {repo._branch.name} has been updated ({git_repo.head.commit})"
        #             )
        #             repo.commit.value = str(git_repo.head.commit)
        #             repo.save()

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

    loop = asyncio.get_event_loop()

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
    aiorun(_start(listen=listen, port=port, interval=interval, debug=debug, config_file=config_file))
