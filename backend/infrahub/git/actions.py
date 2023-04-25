import logging

from infrahub.exceptions import RepositoryError
from infrahub.lock import registry as lock_registry
from infrahub_client import InfrahubClient

from .repository import InfrahubRepository

LOGGER = logging.getLogger("infrahub.git")


async def sync_remote_repositories(client: InfrahubClient) -> None:
    branches = await client.branch.all()
    repositories = await client.get_list_repositories(branches=branches)

    for repo_name, repository in repositories.items():
        async with lock_registry.get(repo_name):
            init_failed = False
            try:
                repo = await InfrahubRepository.init(
                    id=repository.id, name=repository.name, location=repository.location, client=client
                )
            except RepositoryError as excinfo:
                LOGGER.error(excinfo)
                init_failed = True

            if init_failed:
                try:
                    repo = await InfrahubRepository.new(
                        id=repository.id, name=repository.name, location=repository.location, client=client
                    )
                    await repo.import_objects_from_files(branch_name=repo.default_branch_name)
                except RepositoryError as excinfo:
                    LOGGER.error(excinfo)
                    continue

            await repo.sync()
