from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RefreshSettingsResponseDelay(InfrahubMessage):
    """Broadcast to update the API response delay on every running API worker process."""

    response_delay: int = Field(..., ge=0, description="Delay in seconds to add to each API request")
