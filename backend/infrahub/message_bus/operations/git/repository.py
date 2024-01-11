from infrahub import lock
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def add(message: messages.GitRepositoryAdd, service: InfrahubServices) -> None:
    log.info("Cloning and importing repository", repository=message.repository_name, location=message.location)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        repo = await InfrahubRepository.new(
            id=message.repository_id, name=message.repository_name, location=message.location, client=service.client
        )
        await repo.import_objects_from_files(branch_name=repo.default_branch_name)
        await repo.sync()


async def add_read_only(message: messages.GitRepositoryAddReadOnly, service: InfrahubServices) -> None:
    log.info("Cloning and importing repository", repository=message.repository_name, location=message.location)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        repo = await InfrahubReadOnlyRepository.new(
            id=message.repository_id,
            name=message.repository_name,
            location=message.location,
            client=service.client,
            ref=message.ref,
            infrahub_branch_name=message.infrahub_branch_name,
        )
        await repo.import_objects_from_files(branch_name=message.infrahub_branch_name)
        await repo.sync_from_remote()


async def pull_read_only(message: messages.GitRepositoryPullReadOnly, service: InfrahubServices) -> None:
    if not message.ref and not message.commit:
        log.warning(
            "No commit or ref in GitRepositoryPullReadOnly message",
            name=message.repository_name,
            repository_id=message.repository_id,
        )
        return
    log.info(
        "Pulling read-only repository",
        repository=message.repository_name,
        location=message.location,
        ref=message.ref,
        commit=message.commit,
    )
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        init_failed = False
        try:
            repo = await InfrahubReadOnlyRepository.init(
                id=message.repository_id,
                name=message.repository_name,
                location=message.location,
                client=service.client,
                ref=message.ref,
                infrahub_branch_name=message.infrahub_branch_name,
            )
        except RepositoryError:
            init_failed = True

        if init_failed:
            repo = await InfrahubReadOnlyRepository.new(
                id=message.repository_id,
                name=message.repository_name,
                location=message.location,
                client=service.client,
                ref=message.ref,
                infrahub_branch_name=message.infrahub_branch_name,
            )

        await repo.import_objects_from_files(branch_name=message.infrahub_branch_name, commit=message.commit)
        await repo.sync_from_remote(commit=message.commit)


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
