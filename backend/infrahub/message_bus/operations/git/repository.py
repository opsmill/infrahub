from prefect import flow

from infrahub import lock
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository, get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.services import InfrahubServices

log = get_logger()


@flow(name="git-repository-add-read-write")
async def add(message: messages.GitRepositoryAdd, service: InfrahubServices) -> None:
    log.info(
        "Cloning and importing repository",
        repository=message.repository_name,
        location=message.location,
        internal_status=message.internal_status,
    )
    async with service.git_report(
        related_node=message.repository_id,
        title=f"Initial import of the repository in branch: {message.infrahub_branch_name}",
        created_by=message.created_by,
    ) as git_report:
        async with lock.registry.get(name=message.repository_name, namespace="repository"):
            repo = await InfrahubRepository.new(
                id=message.repository_id,
                name=message.repository_name,
                location=message.location,
                client=service.client,
                task_report=git_report,
                infrahub_branch_name=message.infrahub_branch_name,
                internal_status=message.internal_status,
                default_branch_name=message.default_branch_name,
            )
            await repo.import_objects_from_files(
                infrahub_branch_name=message.infrahub_branch_name, git_branch_name=message.default_branch_name
            )
            if message.internal_status == RepositoryInternalStatus.ACTIVE.value:
                await repo.sync()


@flow(name="git-repository-add-read-only")
async def add_read_only(message: messages.GitRepositoryAddReadOnly, service: InfrahubServices) -> None:
    log.info(
        "Cloning and importing read-only repository", repository=message.repository_name, location=message.location
    )
    async with service.git_report(
        related_node=message.repository_id,
        title="Adding Repository",
        created_by=message.created_by,
    ) as git_report:
        async with lock.registry.get(name=message.repository_name, namespace="repository"):
            repo = await InfrahubReadOnlyRepository.new(
                id=message.repository_id,
                name=message.repository_name,
                location=message.location,
                client=service.client,
                ref=message.ref,
                infrahub_branch_name=message.infrahub_branch_name,
                task_report=git_report,
            )
            await repo.import_objects_from_files(infrahub_branch_name=message.infrahub_branch_name)
            if message.internal_status == RepositoryInternalStatus.ACTIVE.value:
                await repo.sync_from_remote()


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
    async with service.git_report(
        related_node=message.repository_id, title="Pulling read-only repository"
    ) as git_report:
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
                    task_report=git_report,
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
                    task_report=git_report,
                )

            await repo.import_objects_from_files(
                infrahub_branch_name=message.infrahub_branch_name, commit=message.commit
            )
            await repo.sync_from_remote(commit=message.commit)


async def merge(message: messages.GitRepositoryMerge, service: InfrahubServices) -> None:
    log.info(
        "Merging repository branch",
        repository_name=message.repository_name,
        repository_id=message.repository_id,
        source_branch=message.source_branch,
        destination_branch=message.destination_branch,
    )

    repo = await InfrahubRepository.init(
        id=message.repository_id,
        name=message.repository_name,
        client=service.client,
        default_branch_name=message.default_branch,
    )

    if message.internal_status == RepositoryInternalStatus.STAGING.value:
        repo_source = await service.client.get(
            kind=InfrahubKind.GENERICREPOSITORY, id=message.repository_id, branch=message.source_branch
        )
        repo_main = await service.client.get(kind=InfrahubKind.GENERICREPOSITORY, id=message.repository_id)
        repo_main.internal_status.value = RepositoryInternalStatus.ACTIVE.value
        repo_main.sync_status.value = repo_source.sync_status.value

        commit = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
        repo_main.commit.value = commit

        await repo_main.save()

    else:
        async with lock.registry.get(name=message.repository_name, namespace="repository"):
            await repo.merge(source_branch=message.source_branch, dest_branch=message.destination_branch)
