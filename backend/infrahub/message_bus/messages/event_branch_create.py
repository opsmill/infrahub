from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import MessagePriority


class EventBranchCreate(InfrahubMessage):
    """Sent when a new branch is created."""

    _priority: MessagePriority = MessagePriority.HIGEST
    branch: str = Field(..., description="The branch that was created")
    branch_id: str = Field(..., description="The unique ID of the branch")
    data_only: bool = Field(
        ..., description="Indicates if this is a data only branch, or repositories can be tied to it."
    )
