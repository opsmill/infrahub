from __future__ import annotations

from pydantic import Field

from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.repository.connectivity"


class GitRepositoryConnectivity(InfrahubMessage):
    """Validate connectivity and credentials to remote repository."""

    repository_name: str = Field(..., description="The name of the repository")
    repository_location: str = Field(..., description="The location of repository")
    default_branch: str | None = Field(
        default=None, description="The branch that must exist on the remote; when unset, only connectivity is checked"
    )


class GitRepositoryConnectivityResponseData(InfrahubResponseData):
    message: str = Field(..., description="The status message")
    success: bool = Field(...)
    operational_status: str = Field(
        ..., description="The operational status the repository should reflect after the connectivity check"
    )


class GitRepositoryConnectivityResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GitRepositoryConnectivityResponseData = Field(default=...)
