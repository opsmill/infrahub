from prefect import flow

from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository, get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.services import InfrahubServices
from infrahub.worker import WORKER_IDENTITY

log = get_logger()


@flow(name="git-repository-check-connectivity")
async def connectivity(message: messages.GitRepositoryConnectivity, service: InfrahubServices) -> None:
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
        await service.reply(message=response, initiator=message)


@flow(name="git-repository-import-object")
async def import_objects(message: messages.GitRepositoryImportObjects, service: InfrahubServices) -> None:
    async with service.git_report(
        related_node=message.repository_id,
        title=f"Processing repository ({message.repository_name})",
    ) as git_report:
        repo = await get_initialized_repo(
            repository_id=message.repository_id,
            name=message.repository_name,
            service=service,
            repository_kind=message.repository_kind,
        )
        repo.task_report = git_report
        await repo.import_objects_from_files(infrahub_branch_name=message.infrahub_branch_name, commit=message.commit)


@flow(name="refresh-git-clone")
async def clone(message: messages.RefreshGitClone, service: InfrahubServices) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git clone request originating from self", worker=WORKER_IDENTITY)
        return

    log.info("Cloning repository", repository=message.repository_id, location=message.location)

    repo = await InfrahubRepository.new(
        id=message.repository_id,
        name=message.repository_name,
        location=message.location,
        client=service.client,
        infrahub_branch_name=message.infrahub_branch_name,
        default_branch_name=message.default_branch_name,
    )
    await repo.fetch()


@flow(name="refresh-git-fetch")
async def fetch(message: messages.RefreshGitFetch, service: InfrahubServices) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git fetch request originating from self", worker=WORKER_IDENTITY)
        return

    log.info("Fetching repository", repository=message.repository_id)

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    # Ensure the repository exists locally
    if repo.validate_directory_root_exists():
        await repo.create_locally(infrahub_branch_name=message.infrahub_branch_name)
    await repo.fetch()
