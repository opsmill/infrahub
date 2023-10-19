from typing import List

from infrahub.log import get_logger
from infrahub.message_bus import InfrahubBaseMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def create(message: messages.EventBranchCreate, service: InfrahubServices) -> None:
    log.info("run_message", branch=message.branch)

    events: List[InfrahubBaseMessage] = [messages.RefreshRegistryBranches()]
    if not message.data_only:
        events.append(messages.RequestGitCreateBranch(branch=message.branch, branch_id=message.branch_id))

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def merge(message: messages.EventBranchMerge, service: InfrahubServices) -> None:
    log.info("Branch merged", source_branch=message.source_branch, target_branch=message.target_branch)

    events: List[InfrahubBaseMessage] = [messages.TriggerArtifactDefinitionGenerate(branch=message.target_branch)]

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
