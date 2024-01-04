import json

from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def configuration(
    message: messages.RefreshWebhookConfiguration,  # pylint: disable=unused-argument
    service: InfrahubServices,
) -> None:
    webhooks = await service.client.all(kind="CoreWebhook")
    expected_webhooks = []
    for webhook in webhooks:
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

    cached_webhooks = await service.cache.list_keys(filter_pattern="webhook:active:*")
    for cached_webhook in cached_webhooks:
        if cached_webhook not in expected_webhooks:
            await service.cache.delete(key=cached_webhook)
