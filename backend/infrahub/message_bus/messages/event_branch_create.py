from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class EventBranchCreate(InfrahubMessage):
    """Sent a new branch is created."""

    branch: str = Field(..., description="The branch that was created")
    branch_id: str = Field(..., description="The unique ID of the branch")
    data_only: bool = Field(
        ..., description="Indicates if this is a data only branch, or repositories can be tied to it."
    )
