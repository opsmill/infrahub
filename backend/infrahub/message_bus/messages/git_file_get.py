from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class GitFileGet(InfrahubMessage):
    """Read a file from a Git repository."""

    commit: str = Field(..., description="The commit id to use to access the file")
    file: str = Field(..., description="The path and filename within the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
