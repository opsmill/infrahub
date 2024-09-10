from typing import List

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId
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
    component_registry = get_component_registry()
    default_branch = registry.get_branch_from_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=service.database, branch=default_branch)
    # send diff update requests for every branch-tracking diff
    branch_diff_roots = await diff_repository.get_empty_roots(base_branch_names=[message.target_branch])

    for diff_root in branch_diff_roots:
        if (
            diff_root.base_branch_name != diff_root.diff_branch_name
            and diff_root.tracking_id
            and isinstance(diff_root.tracking_id, BranchTrackingId)
        ):
            events.append(messages.RequestDiffUpdate(branch_name=diff_root.diff_branch_name))

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

    # for every diff that touches the rebased branch, recalculate it
    component_registry = get_component_registry()
    default_branch = registry.get_branch_from_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=service.database, branch=default_branch)
    diff_roots_to_refresh = await diff_repository.get_empty_roots(diff_branch_names=[message.branch])

    for diff_root in diff_roots_to_refresh:
        if diff_root.base_branch_name != diff_root.diff_branch_name:
            events.append(messages.RequestDiffRefresh(branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid))

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
