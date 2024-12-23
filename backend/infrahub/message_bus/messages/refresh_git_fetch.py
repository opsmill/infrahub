from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RefreshGitFetch(InfrahubMessage):
    """Fetch a repository remote changes."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
