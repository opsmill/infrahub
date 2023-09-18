from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class GitBranchCreate(InfrahubBaseMessage):
    """Create a branch in a Git repository."""

    branch: str = Field(..., description="Name of the branch to create")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
