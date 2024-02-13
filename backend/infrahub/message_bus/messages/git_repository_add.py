from typing import Optional

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class GitRepositoryAdd(InfrahubMessage):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    default_branch_name: Optional[str] = Field(None, description="Default branch for this repository")
