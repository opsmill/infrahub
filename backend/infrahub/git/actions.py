from infrahub import lock
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.services import InfrahubServices

from .repository import InfrahubRepository


async def sync_remote_repositories(service: InfrahubServices) -> None:
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
