from typing import List

from infrahub.core.constants import InfrahubKind
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def mutated(
    message: messages.EventNodeMutated,
    service: InfrahubServices,
) -> None:
    log.debug(
        "Mutation on node",
        branch=message.branch,
        node_id=message.node_id,
        action=message.action,
        kind=message.kind,
        data=message.data,
    )
    events: List[InfrahubMessage] = []
    kind_map = {InfrahubKind.WEBHOOK: [messages.RefreshWebhookConfiguration()]}
    events.extend(kind_map.get(message.kind, []))
    events.append(
        messages.TriggerWebhookActions(event_type=f"{message.kind}.{message.action}", event_data=message.data)
    )
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
