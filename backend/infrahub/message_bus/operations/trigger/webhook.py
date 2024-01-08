from typing import List

from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices


async def actions(message: messages.TriggerWebhookActions, service: InfrahubServices) -> None:
    webhooks = await service.cache.list_keys(filter_pattern="webhook:active:*")
    events: List[InfrahubMessage] = []
    for webhook in webhooks:
        webhook_id = webhook.split(":")[-1]
        events.append(
            messages.SendWebhookEvent(
                webhook_id=webhook_id, event_type=message.event_type, event_data=message.event_data
            )
        )
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
