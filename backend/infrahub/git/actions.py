from infrahub import lock
from infrahub.exceptions import RepositoryError
from infrahub.log import get_logger
from infrahub.services import InfrahubServices

from .repository import InfrahubRepository

log = get_logger(name="infrahub.git")


async def sync_remote_repositories(service: InfrahubServices) -> None:
    branches = await service.client.branch.all()
    repositories = await service.client.get_list_repositories(branches=branches)

    for repo_name, repository in repositories.items():
        async with lock.registry.get(name=repo_name, namespace="repository"):
            init_failed = False
            try:
                repo = await InfrahubRepository.init(
                    service=service,
                    id=repository.id,
                    name=repository.name,
                    location=repository.location,
                    client=service.client,
                )
            except RepositoryError as exc:
                log.error(exc)
                init_failed = True

            if init_failed:
                try:
                    repo = await InfrahubRepository.new(
                        service=service,
                        id=repository.id,
                        name=repository.name,
                        location=repository.location,
                        client=service.client,
                    )
                    await repo.import_objects_from_files(branch_name=repo.default_branch_name)
                except RepositoryError as exc:
                    log.error(exc)
                    continue

            await repo.sync()
