from infrahub.core.constants import InfrahubKind, ProposedChangeState
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def cancel(message: messages.TriggerProposedChangeCancel, service: InfrahubServices) -> None:
    proposed_changed_opened = await service.client.filters(
        kind=InfrahubKind.PROPOSEDCHANGE, include=["id", "source_branch"], state__value=ProposedChangeState.OPEN.value
    )
    proposed_changed_closed = await service.client.filters(
        kind=InfrahubKind.PROPOSEDCHANGE, include=["id", "source_branch"], state__value=ProposedChangeState.CLOSED.value
    )

    events = []
    for proposed_change in proposed_changed_opened + proposed_changed_closed:
        if proposed_change.source_branch.value == message.branch:
            events.append(messages.RequestProposedChangeCancel(proposed_change=proposed_change.id))

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
