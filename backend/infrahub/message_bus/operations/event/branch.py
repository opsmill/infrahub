from typing import List

from prefect import flow

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.models import RequestDiffRefresh, RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.dependencies.registry import get_component_registry
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CREATE_BRANCH,
    REQUEST_DIFF_REFRESH,
    REQUEST_DIFF_UPDATE,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)

log = get_logger()


@flow(name="event-branch-create")
async def create(message: messages.EventBranchCreate, service: InfrahubServices) -> None:
    log.info("run_message", branch=message.branch)

    events: List[InfrahubMessage] = [messages.RefreshRegistryBranches()]
    if message.sync_with_git:
        await service.workflow.submit_workflow(
            workflow=GIT_REPOSITORIES_CREATE_BRANCH,
            parameters={"branch": message.branch, "branch_id": message.branch_id},
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


@flow(name="branch-event-merge")
async def merge(message: messages.EventBranchMerge, service: InfrahubServices) -> None:
    log.info("Branch merged", source_branch=message.source_branch, target_branch=message.target_branch)

    events: List[InfrahubMessage] = [
        messages.RefreshRegistryBranches(),
    ]
    component_registry = get_component_registry()
    default_branch = registry.get_branch_from_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=service.database, branch=default_branch)
    # send diff update requests for every branch-tracking diff
    branch_diff_roots = await diff_repository.get_empty_roots(base_branch_names=[message.target_branch])

    await service.workflow.submit_workflow(
        workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
        parameters={"branch": message.target_branch},
    )

    await service.workflow.submit_workflow(
        workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
        parameters={"branch": message.target_branch},
    )

    for diff_root in branch_diff_roots:
        if (
            diff_root.base_branch_name != diff_root.diff_branch_name
            and diff_root.tracking_id
            and isinstance(diff_root.tracking_id, BranchTrackingId)
        ):
            request_diff_update_model = RequestDiffUpdate(branch_name=diff_root.diff_branch_name)
            await service.workflow.submit_workflow(
                workflow=REQUEST_DIFF_UPDATE, parameters={"model": request_diff_update_model}
            )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


@flow(name="event-branch-rebased")
async def rebased(message: messages.EventBranchRebased, service: InfrahubServices) -> None:
    log.info("Branch rebased", branch=message.branch)

    events: List[InfrahubMessage] = [
        messages.RefreshRegistryRebasedBranch(branch=message.branch),
    ]

    # for every diff that touches the rebased branch, recalculate it
    component_registry = get_component_registry()
    default_branch = registry.get_branch_from_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=service.database, branch=default_branch)
    diff_roots_to_refresh = await diff_repository.get_empty_roots(diff_branch_names=[message.branch])

    for diff_root in diff_roots_to_refresh:
        if diff_root.base_branch_name != diff_root.diff_branch_name:
            request_diff_refresh_model = RequestDiffRefresh(
                branch_name=diff_root.diff_branch_name, diff_id=diff_root.uuid
            )
            await service.workflow.submit_workflow(
                workflow=REQUEST_DIFF_REFRESH, parameters={"model": request_diff_refresh_model}
            )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
