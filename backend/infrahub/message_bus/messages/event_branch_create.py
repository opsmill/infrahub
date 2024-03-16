from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class EventBranchCreate(InfrahubMessage):
    """Sent a new branch is created."""

    branch: str = Field(..., description="The branch that was created")
    branch_id: str = Field(..., description="The unique ID of the branch")
    sync_with_git: bool = Field(..., description="Indicates if Infrahub should extend this branch to git.")
