from typing import List

from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def create_branch(message: messages.RequestGitCreateBranch, service: InfrahubServices):
    """Request to the creation of git branches in available repositories."""
    log.info("Querying repositories for branch creation")
    repositories = await service.client.filters(kind="CoreRepository")
    events: List[messages.GitBranchCreate] = []
    for repository in repositories:
        events.append(
            messages.GitBranchCreate(
                branch=message.branch,
                branch_id=message.branch_id,
                repository_name=repository.name.value,
                repository_id=repository.id,
            )
        )
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
