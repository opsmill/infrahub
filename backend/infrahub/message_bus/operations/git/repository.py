from prefect import flow
from prefect.logging import get_run_logger

from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository, get_initialized_repo, initialize_repo
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.services import InfrahubServices
from infrahub.worker import WORKER_IDENTITY


@flow(name="git-repository-check-connectivity", flow_run_name="Check connectivity for {message.repository_name}")
async def connectivity(message: messages.GitRepositoryConnectivity, service: InfrahubServices) -> None:
    response_data = GitRepositoryConnectivityResponseData(message="Successfully accessed repository", success=True)
    log = get_run_logger()

    try:
        InfrahubRepository.check_connectivity(name=message.repository_name, url=message.repository_location)
        log.info(response_data.message)
    except RepositoryError as exc:
        response_data.success = False
        response_data.message = exc.message
        log.error(exc.message)

    if message.reply_requested:
        response = GitRepositoryConnectivityResponse(
            data=response_data,
        )
        await service.reply(message=response, initiator=message)


@flow(name="refresh-git-fetch", flow_run_name="Fetch git repository {message.repository_name} on " + WORKER_IDENTITY)
async def fetch(message: messages.RefreshGitFetch, service: InfrahubServices) -> None:
    log = get_run_logger()
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git fetch request originating from self ({WORKER_IDENTITY})")
        return

    try:
        repo = await get_initialized_repo(
            repository_id=message.repository_id,
            name=message.repository_name,
            service=service,
            repository_kind=message.repository_kind,
        )
    except RepositoryError:
        repo = await initialize_repo(
            location=message.location,
            repository_id=message.repository_id,
            name=message.repository_name,
            service=service,
            repository_kind=message.repository_kind,
        )

    await repo.fetch()
    await repo.pull(branch_name=message.infrahub_branch_name)
