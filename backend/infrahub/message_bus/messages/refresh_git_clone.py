from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RefreshGitClone(InfrahubMessage):
    """Clone a repository locally."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")
    default_branch_name: str | None = Field(None, description="Default branch for this repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
