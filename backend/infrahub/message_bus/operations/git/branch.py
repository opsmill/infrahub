from prefect import flow

from infrahub import lock
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


@flow(name="git-repository-branch-create")
async def create(message: messages.GitBranchCreate, service: InfrahubServices) -> None:
    log.info("creating branch in repository", branch=message.branch, repository=message.repository_name)
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=service.client)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        await repo.create_branch_in_git(branch_name=message.branch, branch_id=message.branch_id)
