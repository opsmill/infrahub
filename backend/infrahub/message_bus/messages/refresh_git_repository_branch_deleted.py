from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RefreshGitRepositoryBranchDeleted(InfrahubMessage):
    """Notify workers that a branch was deleted from the remote repository."""

    repository_id: str = Field(..., description="The unique ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    branch_name: str = Field(..., description="The name of the branch that was deleted")
