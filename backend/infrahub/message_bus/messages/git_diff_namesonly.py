from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class GitDiffNamesOnly(InfrahubMessage):
    """Request a list of modified files between two commits."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    first_commit: str = Field(..., description="The first commit")
    second_commit: str = Field(..., description="The second commit")
