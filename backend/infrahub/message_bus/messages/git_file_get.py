from pydantic import Field

from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.file.get"


class GitFileGet(InfrahubMessage):
    """Read a file from a Git repository."""

    commit: str = Field(..., description="The commit id to use to access the file")
    file: str = Field(..., description="The path and filename within the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")


class GitFileGetResponseData(InfrahubResponseData):
    content: str | None = None  # is empty if error_message / http_code are not empty
    error_message: str | None = None
    http_code: int | None = None


class GitFileGetResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GitFileGetResponseData
