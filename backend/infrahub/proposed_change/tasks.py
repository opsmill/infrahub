from __future__ import annotations

from infrahub_sdk.protocols import CoreProposedChange
from prefect import flow, task
from prefect.client.schemas.objects import (
    State,  # noqa: TCH002
)
from prefect.logging import get_run_logger
from prefect.states import Completed, Failed

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.protocols import CoreDataCheck, CoreValidator
from infrahub.core.protocols import CoreProposedChange as InternalCoreProposedChange
from infrahub.dependencies.registry import get_component_registry
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.proposed_change.models import (
    RequestProposedChangeDataIntegrity,  # noqa: TCH001. as symbol is required by prefect flow
)
from infrahub.services import services


async def _proposed_change_transition_state(
    state: ProposedChangeState,
    proposed_change: InternalCoreProposedChange | None = None,
    proposed_change_id: str | None = None,
) -> None:
    service = services.service
    async with service.database.start_session() as db:
        if proposed_change is None and proposed_change_id:
            proposed_change = await registry.manager.get_one(
                db=db, id=proposed_change_id, kind=InternalCoreProposedChange, raise_on_error=True
            )
        if proposed_change:
            proposed_change.state.value = state.value  # type: ignore[misc]
            await proposed_change.save(db=db)


# async def proposed_change_transition_merged(flow: Flow, flow_run: FlowRun, state: State) -> None:
#     await _proposed_change_transition_state(
#         proposed_change_id=flow_run.parameters["proposed_change_id"], state=ProposedChangeState.MERGED
#     )


# async def proposed_change_transition_open(flow: Flow, flow_run: FlowRun, state: State) -> None:
#     await _proposed_change_transition_state(
#         proposed_change_id=flow_run.parameters["proposed_change_id"], state=ProposedChangeState.OPEN
#     )


@flow(
    name="proposed-change-merge",
    flow_run_name="Merge propose change: {proposed_change_name} ",
    description="Merge a given proposed change.",
    # TODO need to investigate why these function are not working as expected
    # on_completion=[proposed_change_transition_merged],  # type: ignore
    # on_failure=[proposed_change_transition_open],  # type: ignore
    # on_crashed=[proposed_change_transition_open],  # type: ignore
    # on_cancellation=[proposed_change_transition_open],  # type: ignore
)
async def merge_proposed_change(proposed_change_id: str, proposed_change_name: str) -> State:  # pylint: disable=unused-argument
    service = services.service
    log = get_run_logger()

    async with service.database.start_session() as db:
        proposed_change = await registry.manager.get_one(
            db=db, id=proposed_change_id, kind=InternalCoreProposedChange, raise_on_error=True
        )

        log.info("Validating if all conditions are met to merge the proposed change")

        source_branch = await Branch.get_by_name(db=db, name=proposed_change.source_branch.value)
        validations = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
        for validation in validations.values():
            validator_kind = validation.get_kind()
            if (
                validator_kind != InfrahubKind.DATAVALIDATOR
                and validation.conclusion.value.value != ValidatorConclusion.SUCCESS.value
            ):
                # Ignoring Data integrity checks as they are handled again later
                await _proposed_change_transition_state(proposed_change=proposed_change, state=ProposedChangeState.OPEN)
                return Failed(message="Unable to merge proposed change containing failing checks")
            if validator_kind == InfrahubKind.DATAVALIDATOR:
                data_checks = await validation.checks.get_peers(db=db, peer_type=CoreDataCheck)
                for check in data_checks.values():
                    if check.conflicts.value and not check.keep_branch.value:
                        await _proposed_change_transition_state(
                            proposed_change=proposed_change, state=ProposedChangeState.OPEN
                        )
                        return Failed(
                            message="Data conflicts found on branch and missing decisions about what branch to keep"
                        )

        log.info("Proposed change is eligible to be merged")
        await merge_branch(branch=source_branch.name)

        log.info(f"Branch {source_branch.name} has been merged successfully")

        await _proposed_change_transition_state(proposed_change=proposed_change, state=ProposedChangeState.MERGED)
        return Completed(message="proposed change merged successfully")


@flow(
    name="proposed-changes-cancel-branch",
    flow_run_name="Cancel all proposed change associated with branch {branch_name}",
    description="Cancel all Proposed change associated with a branch.",
)
async def cancel_proposed_changes_branch(branch_name: str) -> None:
    service = services.service
    proposed_changed_opened = await service.client.filters(
        kind=CoreProposedChange,
        include=["id", "source_branch"],
        state__value=ProposedChangeState.OPEN.value,
        source_branch__value=branch_name,
    )
    proposed_changed_closed = await service.client.filters(
        kind=CoreProposedChange,
        include=["id", "source_branch"],
        state__value=ProposedChangeState.CLOSED.value,
        source_branch__value=branch_name,
    )

    for proposed_change in proposed_changed_opened + proposed_changed_closed:
        await cancel_proposed_change(proposed_change=proposed_change)


@task(name="Cancel a propose change", description="Cancel a propose change")
async def cancel_proposed_change(proposed_change: CoreProposedChange) -> None:
    service = services.service
    log = get_run_logger()

    log.info("Canceling proposed change as the source branch was deleted")
    proposed_change = await service.client.get(kind=CoreProposedChange, id=proposed_change.id)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()


@flow(
    name="proposed-changed-data-integrity",
    flow_run_name="Triggers data integrity check",
)
async def run_proposed_change_data_integrity_check(model: RequestProposedChangeDataIntegrity) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""

    service = services.service
    destination_branch = await registry.get_branch(db=service.database, branch=model.destination_branch)
    source_branch = await registry.get_branch(db=service.database, branch=model.source_branch)
    component_registry = get_component_registry()
    async with service.database.start_transaction() as dbt:
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbt, branch=source_branch)
        await diff_coordinator.update_branch_diff(base_branch=destination_branch, diff_branch=source_branch)
