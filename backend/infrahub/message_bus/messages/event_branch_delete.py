from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class EventBranchDelete(InfrahubMessage):
    """Sent when a branch has been deleted."""

    branch: str = Field(..., description="The branch that was deleted")
    branch_id: str = Field(..., description="The unique ID of the branch")
    sync_with_git: bool = Field(..., description="Indicates if the branch was extended to Git")
