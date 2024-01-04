from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class GitBranchCreate(InfrahubMessage):
    """Create a branch in a Git repository."""

    branch: str = Field(..., description="Name of the branch to create")
    branch_id: str = Field(..., description="The unique ID of the branch")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
