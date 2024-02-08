from typing import List

from pydantic import Field

from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.diff.names_only"


class GitDiffNamesOnly(InfrahubMessage):
    """Request a list of modified files between two commits."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    first_commit: str = Field(..., description="The first commit")
    second_commit: str = Field(..., description="The second commit")


class GitDiffNamesOnlyResponseData(InfrahubResponseData):
    files_added: List[str] = Field(..., description="Files added")
    files_changed: List[str] = Field(..., description="Files changed")
    files_removed: List[str] = Field(..., description="Files removed")


class GitDiffNamesOnlyResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    response_data: GitDiffNamesOnlyResponseData
