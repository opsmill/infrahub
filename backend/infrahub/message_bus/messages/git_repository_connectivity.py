from __future__ import annotations

from pydantic import Field

from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.repository.connectivity"


class GitRepositoryConnectivity(InfrahubMessage):
    """Validate connectivity and credentials to remote repository"""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    repository_location: str = Field(..., description="The location of repository")


class GitRepositoryConnectivityResponseData(InfrahubResponseData):
    message: str = Field(..., description="The status message")
    success: bool = Field(...)


class GitRepositoryConnectivityResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GitRepositoryConnectivityResponseData = Field(default=...)
