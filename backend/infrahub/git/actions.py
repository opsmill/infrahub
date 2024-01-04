from typing import Dict

from infrahub import lock
from infrahub.exceptions import RepositoryError
from infrahub.services import InfrahubServices

from .repository import InfrahubReadOnlyRepository, InfrahubRepository, InfrahubRepositoryBase


async def sync_remote_repositories(service: InfrahubServices) -> None:
    branches = await service.client.branch.all()
    repositories = await service.client.get_list_repositories(branches=branches)

    repository_class_map: Dict[str, InfrahubRepositoryBase] = {
        "CoreRepository": InfrahubRepository,
        "CoreReadOnlyRepository": InfrahubReadOnlyRepository,
    }

    for repo_name, repository_data in repositories.items():
        repo_class = repository_class_map[repository_data.repository.get_kind()]
        async with lock.registry.get(name=repo_name, namespace="repository"):
            init_failed = False
            try:
                repo = await repo_class.init(
                    service=service,
                    id=repository_data.id,
                    name=repository_data.name,
                    location=repository_data.location,
                    client=service.client,
                )
            except RepositoryError as exc:
                service.log.error(exc.message, repository=exc.identifier)
                init_failed = True

            if init_failed:
                try:
                    repo = await repo_class.new(
                        service=service,
                        id=repository_data.id,
                        name=repository_data.name,
                        location=repository_data.location,
                        client=service.client,
                    )
                    await repo.import_objects_from_files(branch_name=repo.default_branch_name)
                except RepositoryError as exc:
                    service.log.error(exc.message, repository=exc.identifier)
                    continue

            await repo.sync()
