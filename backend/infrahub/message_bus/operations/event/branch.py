from __future__ import annotations

from prefect import flow

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.dependencies.registry import get_component_registry
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.workflows.catalogue import (
    DIFF_UPDATE,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)

log = get_logger()


@flow(name="branch-event-merge")
async def merge(message: messages.EventBranchMerge, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        log.info("Branch merged", source_branch=message.source_branch, target_branch=message.target_branch)

        events: list[InfrahubMessage] = [
            messages.RefreshRegistryBranches(),
        ]
        component_registry = get_component_registry()
        default_branch = registry.get_branch_from_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
        # send diff update requests for every branch-tracking diff
        branch_diff_roots = await diff_repository.get_roots_metadata(base_branch_names=[message.target_branch])

        await service.workflow.submit_workflow(
            workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
            context=message.context,
            parameters={"branch": message.target_branch},
        )

        await service.workflow.submit_workflow(
            workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
            context=message.context,
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
                    workflow=DIFF_UPDATE, context=message.context, parameters={"model": request_diff_update_model}
                )

        for event in events:
            event.assign_meta(parent=message)
            await service.message_bus.send(message=event)
