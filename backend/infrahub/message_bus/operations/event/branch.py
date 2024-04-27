from typing import List

from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def create(message: messages.EventBranchCreate, service: InfrahubServices) -> None:
    log.info("run_message", branch=message.branch)

    events: List[InfrahubMessage] = [messages.RefreshRegistryBranches()]
    if message.sync_with_git:
        events.append(messages.RequestGitCreateBranch(branch=message.branch, branch_id=message.branch_id))

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def delete(message: messages.EventBranchDelete, service: InfrahubServices) -> None:
    log.info("Branch was deleted", branch=message.branch)

    events: List[InfrahubMessage] = [
        messages.RefreshRegistryBranches(),
        messages.TriggerProposedChangeCancel(branch=message.branch),
    ]

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def merge(message: messages.EventBranchMerge, service: InfrahubServices) -> None:
    log.info("Branch merged", source_branch=message.source_branch, target_branch=message.target_branch)

    events: List[InfrahubMessage] = [
        messages.RefreshRegistryBranches(),
        messages.TriggerArtifactDefinitionGenerate(branch=message.target_branch),
        messages.TriggerGeneratorDefinitionRun(branch=message.target_branch),
    ]

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def rebased(message: messages.EventBranchRebased, service: InfrahubServices) -> None:
    log.info("Branch rebased", branch=message.branch)

    events: List[InfrahubMessage] = [
        messages.RefreshRegistryRebasedBranch(branch=message.branch),
    ]
    if message.ipam_node_details:
        events.append(
            messages.TriggerIpamReconciliation(branch=message.branch, ipam_node_details=message.ipam_node_details),
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
