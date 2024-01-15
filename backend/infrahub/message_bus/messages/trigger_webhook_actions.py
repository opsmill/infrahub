from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class TriggerWebhookActions(InfrahubMessage):
    """Triggers webhooks to be sent for the given action"""

    event_type: str = Field(..., description="The event type")
    event_data: dict = Field(..., description="The webhook payload")
