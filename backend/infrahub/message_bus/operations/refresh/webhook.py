import json

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def configuration(
    message: messages.RefreshWebhookConfiguration,  # pylint: disable=unused-argument
    service: InfrahubServices,
) -> None:
    service.log.debug("Refreshing webhook configuration")
    standard_webhooks = await service.client.all(kind=InfrahubKind.WEBHOOK)
    custom_webhooks = await service.client.all(kind="CoreCustomWebhook")

    expected_webhooks = []
    for webhook in standard_webhooks:
        webhook_key = f"webhook:active:{webhook.id}"
        expected_webhooks.append(webhook_key)
        payload = {
            "webhook_type": "standard",
            "webhook_configuration": {
                "url": webhook.url.value,
                "shared_key": webhook.shared_key.value,
                "validate_certificates": webhook.validate_certificates.value,
            },
        }
        await service.cache.set(key=webhook_key, value=json.dumps(payload))

    for webhook in custom_webhooks:
        webhook_key = f"webhook:active:{webhook.id}"
        expected_webhooks.append(webhook_key)
        payload = {
            "webhook_type": "custom",
            "webhook_configuration": {
                "url": webhook.url.value,
                "validate_certificates": webhook.validate_certificates.value,
            },
        }
        if webhook.transformation.id:
            transform = await service.client.get(
                kind="CoreTransformPython",
                id=webhook.transformation.id,
                prefetch_relationships=True,
                populate_store=True,
                include=["name", "class_name", "file_path", "repository"],
            )
            payload["webhook_type"] = "transform"
            payload["webhook_configuration"]["transform_name"] = transform.name.value
            payload["webhook_configuration"]["transform_class"] = transform.class_name.value
            payload["webhook_configuration"]["transform_file"] = transform.file_path.value
            payload["webhook_configuration"]["repository_id"] = transform.repository.id
            payload["webhook_configuration"]["repository_name"] = transform.repository.peer.name.value

        await service.cache.set(key=webhook_key, value=json.dumps(payload))

    cached_webhooks = await service.cache.list_keys(filter_pattern="webhook:active:*")
    for cached_webhook in cached_webhooks:
        if cached_webhook not in expected_webhooks:
            await service.cache.delete(key=cached_webhook)
