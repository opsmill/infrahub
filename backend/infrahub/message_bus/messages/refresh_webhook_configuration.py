from infrahub.message_bus import InfrahubMessage


class RefreshWebhookConfiguration(InfrahubMessage):
    """Sent to indicate that configuration in the cache for webhooks should be refreshed."""
