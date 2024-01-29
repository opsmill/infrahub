import json
from typing import Dict, Type

from infrahub.core.constants import Severity
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.webhook import CustomWebhook, StandardWebhook, TransformWebhook, Webhook


async def event(message: messages.SendWebhookEvent, service: InfrahubServices) -> None:
    webhook_definition = await service.cache.get(key=f"webhook:active:{message.webhook_id}")
    if not webhook_definition:
        service.log.warning("Webhook not found", webhook_id=message.webhook_id)
        return

    webhook_data = json.loads(webhook_definition)
    payload = {"event_type": message.event_type, "data": message.event_data, "service": service}
    webhook_map: Dict[str, Type[Webhook]] = {
        "standard": StandardWebhook,
        "custom": CustomWebhook,
        "transform": TransformWebhook,
    }
    webhook_class = webhook_map[webhook_data["webhook_type"]]
    payload.update(webhook_data["webhook_configuration"])
    webhook = webhook_class(**payload)
    try:
        await webhook.send()
        if message.meta.task_id:
            log = messages.LogTaskResult(
                task_id=message.meta.task_id,
                title=webhook.webhook_type,
                message="Successfully sent webhook",
                related_node=message.webhook_id,
                success=True,
                severity=Severity.INFO,
            )
            await service.send(log)
    except Exception as exc:
        if message.meta.task_id:
            log = messages.LogTaskResult(
                task_id=message.meta.task_id,
                title=webhook.webhook_type,
                message=str(exc),
                related_node=message.webhook_id,
                success=False,
                severity=Severity.ERROR,
            )
            await service.send(log)
        raise exc
