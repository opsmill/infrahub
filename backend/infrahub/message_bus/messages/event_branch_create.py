from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class EventBranchCreate(InfrahubBaseMessage):
    """Sent a new branch is created."""

    branch: str = Field(..., description="The branch that was created")
