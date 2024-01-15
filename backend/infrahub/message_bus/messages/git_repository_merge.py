from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class GitRepositoryMerge(InfrahubMessage):
    """Merge one branch into another."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    source_branch: str = Field(..., description="The source branch")
    destination_branch: str = Field(..., description="The source branch")
