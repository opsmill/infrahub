from prefect import flow

from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository, get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_client, get_message_bus

log = get_logger()


@flow(name="git-repository-check-connectivity", flow_run_name="Check connectivity for {message.repository_name}")
async def connectivity(message: messages.GitRepositoryConnectivity) -> None:
    response_data = GitRepositoryConnectivityResponseData(message="Successfully accessed repository", success=True)

    try:
        InfrahubRepository.check_connectivity(name=message.repository_name, url=message.repository_location)
    except RepositoryError as exc:
        response_data.success = False
        response_data.message = exc.message

    if message.reply_requested:
        response = GitRepositoryConnectivityResponse(
            data=response_data,
        )
        message_bus = await get_message_bus()
        await message_bus.reply_if_initiator_meta(message=response, initiator=message)


@flow(name="refresh-git-fetch", flow_run_name="Fetch git repository {message.repository_name} on " + WORKER_IDENTITY)
async def fetch(message: messages.RefreshGitFetch) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git fetch request originating from self", worker=WORKER_IDENTITY)
        return

    repo = await get_initialized_repo(
        client=get_client(),
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
    )

    await repo.fetch()
    await repo.pull(
        branch_name=message.infrahub_branch_name,
        branch_id=message.infrahub_branch_id,
        create_if_missing=True,
        update_commit_value=False,
    )
