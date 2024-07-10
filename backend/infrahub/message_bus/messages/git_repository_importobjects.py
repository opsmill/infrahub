from __future__ import annotations

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class GitRepositoryImportObjects(InfrahubMessage):
    """Re run import job against an existing commit."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    commit: str = Field(..., description="Specific commit to pull")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
