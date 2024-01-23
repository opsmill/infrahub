from infrahub import lock
from infrahub.exceptions import RepositoryError
from infrahub.services import InfrahubServices

from .repository import InfrahubRepository


async def sync_remote_repositories(service: InfrahubServices) -> None:
    branches = await service.client.branch.all()
    repositories = await service.client.get_list_repositories(branches=branches, kind="CoreRepository")

    for repo_name, repository_data in repositories.items():
        async with lock.registry.get(name=repo_name, namespace="repository"):
            init_failed = False
            try:
                repo = await InfrahubRepository.init(
                    service=service,
                    id=repository_data.repository.id,
                    name=repository_data.repository.name.value,
                    location=repository_data.repository.location.value,
                    client=service.client,
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
                    )
                    await repo.import_objects_from_files(branch_name=repo.default_branch_name)
                except RepositoryError as exc:
                    service.log.error(str(exc))
                    continue

            await repo.sync()
