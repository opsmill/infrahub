import json

import httpx

from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def event(message: messages.SendWebhookEvent, service: InfrahubServices) -> None:
    webhook_definition = await service.cache.get(key=f"webhook:active:{message.webhook_id}")
    if not webhook_definition:
        service.log.warning("Webhook not found", webhook_id=message.webhook_id)
        return

    webhook = json.loads(webhook_definition)
    payload = {"event_type": message.event_type, "data": message.event_data}

    async with httpx.AsyncClient(verify=webhook["webhook_configuration"]["validate_certificates"]) as client:
        await client.post(webhook["webhook_configuration"]["url"], json=payload)
