from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class EventBranchCreate(InfrahubBaseMessage):
    """Sent a new branch is created."""

    branch: str = Field(..., description="The branch that was created")
    data_only: bool = Field(
        ..., description="Indicates if this is a data only branch, or repositories can be tied to it."
    )
