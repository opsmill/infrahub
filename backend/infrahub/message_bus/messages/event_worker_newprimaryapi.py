from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class EventWorkerNewPrimaryAPI(InfrahubMessage):
    """Sent on startup or when a new primary API worker is elected."""

    worker_id: str = Field(..., description="The worker ID that got elected")
