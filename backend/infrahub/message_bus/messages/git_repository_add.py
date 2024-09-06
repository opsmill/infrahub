from typing import Optional

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class GitRepositoryAdd(InfrahubMessage):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    created_by: Optional[str] = Field(default=None, description="The user ID of the user that created the repository")
    default_branch_name: Optional[str] = Field(None, description="Default branch for this repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    internal_status: str = Field(..., description="Administrative status of the repository")
