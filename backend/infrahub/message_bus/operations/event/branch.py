from typing import List

from infrahub.core import registry
from infrahub.core.diff.model.path import EnrichedDiffRoot, NameTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.dependencies.registry import get_component_registry
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
        messages.TriggerIpamReconciliation(branch=message.target_branch, ipam_node_details=message.ipam_node_details),
        messages.TriggerArtifactDefinitionGenerate(branch=message.target_branch),
        messages.TriggerGeneratorDefinitionRun(branch=message.target_branch),
    ]
    open_branch_diffs = await get_diff_roots_for_open_branches(service=service)
    for diff in open_branch_diffs:
        if diff.tracking_id:
            if isinstance(diff.tracking_id, NameTrackingId):
                name = diff.tracking_id.name
            else:
                name = None
            events.append(messages.RequestDiffUpdate(branch_name=diff.diff_branch_name, name=name))

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

    open_branch_diffs = await get_diff_roots_for_open_branches(service=service)
    for diff in open_branch_diffs:
        if diff.tracking_id:
            events.append(
                messages.RequestDiffRefresh(
                    branch_name=diff.diff_branch_name, tracking_id_str=diff.tracking_id.serialize()
                )
            )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def get_diff_roots_for_open_branches(service: InfrahubServices) -> list[EnrichedDiffRoot]:
    component_registry = get_component_registry()
    default_branch = registry.get_branch_from_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=service.database, branch=default_branch)
    all_diff_roots = await diff_repository.get_empty_roots()
    open_branch_names = set()
    for branch_name in registry.branch:
        branch = registry.get_branch_from_registry(branch=branch_name)
        if branch.status == "OPEN":
            open_branch_names.add(branch.name)
    return [dr for dr in all_diff_roots if dr.diff_branch_name in open_branch_names]
