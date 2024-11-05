from __future__ import annotations

from infrahub_sdk.protocols import CoreProposedChange
from prefect import flow, task
from prefect.logging import get_run_logger

from infrahub.core.constants import ProposedChangeState
from infrahub.services import (
    services,
)


@flow(name="proposed-changes-cancel-branch", description="Cancel all Proposed change associated with a branch.")
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


@task(description="Cancel a propose change")
async def cancel_proposed_change(proposed_change: CoreProposedChange) -> None:
    service = services.service
    log = get_run_logger()

    log.info("Canceling proposed change as the source branch was deleted")
    proposed_change = await service.client.get(kind=CoreProposedChange, id=proposed_change.id)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()
