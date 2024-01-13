from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class EventBranchDelete(InfrahubMessage):
    """Sent when a branch has been deleted."""

    branch: str = Field(..., description="The branch that was deleted")
    branch_id: str = Field(..., description="The unique ID of the branch")
    data_only: bool = Field(
        ..., description="Indicates if this is a data only branch, or repositories can be tied to it."
    )
