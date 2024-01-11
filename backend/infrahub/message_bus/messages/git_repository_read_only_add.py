from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class GitRepositoryAddReadOnly(InfrahubMessage):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    ref: str = Field(..., description="Ref to track on the external repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
