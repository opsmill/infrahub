from __future__ import annotations

from typing import Optional

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class GitRepositoryPullReadOnly(InfrahubMessage):
    """Update a read-only repository to the latest commit for its ref"""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    ref: Optional[str] = Field(None, description="Ref to track on the external repository")
    commit: Optional[str] = Field(None, description="Specific commit to pull")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
