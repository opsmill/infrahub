from pydantic import BaseModel, Field

from infrahub.message_bus import InfrahubMessage


class SendWebhookData(BaseModel):
    """Sent a webhook to an external source."""

    webhook_id: str = Field(..., description="The unique ID of the webhook")
    event_type: str = Field(..., description="The event type")
    event_data: dict = Field(..., description="The data tied to the event")


class SendWebhookEvent(SendWebhookData, InfrahubMessage):
    """Sent a webhook to an external source."""
