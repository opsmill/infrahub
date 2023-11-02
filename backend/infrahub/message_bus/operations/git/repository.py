from infrahub import lock
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def add(message: messages.GitRepositoryAdd, service: InfrahubServices) -> None:
    log.info("Cloning and importing repositoryy", repository=message.repository_name, location=message.location)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        repo = await InfrahubRepository.new(
            id=message.repository_id, name=message.repository_name, location=message.location, client=service.client
        )
        await repo.import_objects_from_files(branch_name=repo.default_branch_name)
        await repo.sync()


async def merge(message: messages.GitRepositoryMerge, service: InfrahubServices) -> None:
    log.info(
        "Merging repository branch",
        repository_name=message.repository_name,
        repository_id=message.repository_id,
        source_branch=message.source_branch,
        destination_branch=message.destination_branch,
    )
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=service.client)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        await repo.merge(source_branch=message.source_branch, dest_branch=message.destination_branch)
