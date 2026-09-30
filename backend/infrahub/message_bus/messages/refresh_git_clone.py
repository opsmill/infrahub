from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RefreshGitClone(InfrahubMessage):
    """Ask every worker to create its local copy of a repository if it has none, without changing any checkout."""

    repository_id: str = Field(..., description="The unique ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch whose ref a new copy checks out")
