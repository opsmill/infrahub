from infrahub_sdk import InfrahubClient
from prefect import flow, task

from infrahub import lock
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.protocols import CoreRepository
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.services import services
from infrahub.workflows.utils import add_branch_tag

from ..log import get_logger
from ..message_bus import messages
from ..tasks.artifact import define_artifact
from .models import RequestArtifactGenerate
from .repository import InfrahubRepository, get_initialized_repo

log = get_logger()


@flow(name="git-repositories-branch-create")
async def create_branch(branch: str, branch_id: str) -> None:
    """Request to the creation of git branches in available repositories."""
    service = services.service
    await add_branch_tag(branch_name=branch)

    repositories: list[CoreRepository] = await service.client.filters(kind=CoreRepository)

    batch = await service.client.create_batch()

    for repository in repositories:
        batch.add(
            task=git_branch_create,
            client=service.client.client,
            branch=branch,
            branch_id=branch_id,
            repository_name=repository.name.value,
            repository_id=repository.id,
        )

    async for _, _ in batch.execute():
        pass


@flow(name="git-repository-sync")
async def sync_remote_repositories() -> None:
    service = services.service

    branches = await service.client.branch.all()
    repositories = await service.client.get_list_repositories(branches=branches, kind=InfrahubKind.REPOSITORY)

    for repo_name, repository_data in repositories.items():
        async with service.git_report(
            title="Syncing repository", related_node=repository_data.repository.id, create_with_context=False
        ) as git_report:
            active_internal_status = RepositoryInternalStatus.ACTIVE.value
            default_internal_status = repository_data.branch_info[registry.default_branch].internal_status
            staging_branch = None
            if default_internal_status != RepositoryInternalStatus.ACTIVE.value:
                active_internal_status = RepositoryInternalStatus.STAGING.value
                staging_branch = repository_data.get_staging_branch()

            infrahub_branch = staging_branch or registry.default_branch

            async with lock.registry.get(name=repo_name, namespace="repository"):
                init_failed = False
                try:
                    repo = await InfrahubRepository.init(
                        service=service,
                        id=repository_data.repository.id,
                        name=repository_data.repository.name.value,
                        location=repository_data.repository.location.value,
                        client=service.client,
                        task_report=git_report,
                        internal_status=active_internal_status,
                        default_branch_name=repository_data.repository.default_branch.value,
                    )
                except RepositoryError as exc:
                    service.log.error(str(exc))
                    init_failed = True

                if init_failed:
                    try:
                        repo = await InfrahubRepository.new(
                            service=service,
                            id=repository_data.repository.id,
                            name=repository_data.repository.name.value,
                            location=repository_data.repository.location.value,
                            client=service.client,
                            task_report=git_report,
                            internal_status=active_internal_status,
                            default_branch_name=repository_data.repository.default_branch.value,
                        )
                        await repo.import_objects_from_files(
                            git_branch_name=registry.default_branch, infrahub_branch_name=infrahub_branch
                        )
                    except RepositoryError as exc:
                        await git_report.error(str(exc))
                        continue

                error: RepositoryError | None = None

                try:
                    await repo.sync(staging_branch=staging_branch)
                except RepositoryError as exc:
                    error = exc

                await git_report.set_status(
                    previous_status=repository_data.repository.operational_status.value, error=error
                )


@task
async def git_branch_create(
    client: InfrahubClient, branch: str, branch_id: str, repository_id: str, repository_name: str
) -> None:
    repo = await InfrahubRepository.init(id=repository_id, name=repository_name, client=client)
    async with lock.registry.get(name=repository_name, namespace="repository"):
        await repo.create_branch_in_git(branch_name=branch, branch_id=branch_id)


@flow(name="artifact-definition-generate")
async def generate_artifact_definition(branch: str) -> None:
    service = services.service
    artifact_definitions = await service.client.all(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch, include=["id"])

    events = [
        messages.RequestArtifactDefinitionGenerate(branch=branch, artifact_definition=artifact_definition.id)
        for artifact_definition in artifact_definitions
    ]
    for event in events:
        await service.send(message=event)


@flow(name="artifact-generate")
async def generate_artifact(model: RequestArtifactGenerate) -> None:
    log.debug("Generating artifact", message=model)

    service = services.service

    repo = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
    )

    artifact = await define_artifact(message=model, service=service)

    try:
        result = await repo.render_artifact(artifact=artifact, message=model)
        log.debug(
            "Generated artifact",
            name=model.artifact_name,
            changed=result.changed,
            checksum=result.checksum,
            artifact_id=result.artifact_id,
            storage_id=result.storage_id,
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Failed to generate artifact", error=exc)
        artifact.status.value = "Error"
        await artifact.save()
