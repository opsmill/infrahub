from typing import List

from infrahub.log import get_logger
from infrahub.message_bus import InfrahubBaseMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def create(message: messages.EventBranchCreate, service: InfrahubServices) -> None:
    log.info("run_message", branch=message.branch)

    events: List[InfrahubBaseMessage] = [messages.RefreshRegistryBranches()]
    if not message.data_only:
        events.append(messages.RequestGitCreateBranch(branch=message.branch))

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
