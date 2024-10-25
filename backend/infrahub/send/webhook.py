from typing import Any

import ujson
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.exceptions import NodeNotFoundError
from infrahub.send.models import SendWebhookData
from infrahub.services import services
from infrahub.webhook import CustomWebhook, StandardWebhook, TransformWebhook, Webhook


@flow(name="event-send-webhook")
async def send_webhook(model: SendWebhookData) -> None:
    service = services.service
    log = get_run_logger()

    webhook_definition = await service.cache.get(key=f"webhook:active:{model.webhook_id}")
    if not webhook_definition:
        log.warning("Webhook not found")
        raise NodeNotFoundError(
            node_type="Webhook", identifier=model.webhook_id, message="The requested Webhook was not found"
        )

    webhook_data = ujson.loads(webhook_definition)
    payload: dict[str, Any] = {"event_type": model.event_type, "data": model.event_data, "service": service}
    webhook_map: dict[str, type[Webhook]] = {
        "standard": StandardWebhook,
        "custom": CustomWebhook,
        "transform": TransformWebhook,
    }
    webhook_class = webhook_map[webhook_data["webhook_type"]]
    payload.update(webhook_data["webhook_configuration"])
    webhook = webhook_class(**payload)
    await webhook.send()

    log.info("Successfully sent webhook")
