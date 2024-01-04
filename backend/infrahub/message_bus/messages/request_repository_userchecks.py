from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class RequestRepositoryUserChecks(InfrahubMessage):
    """Sent to trigger the user defined checks on a repository."""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository: str = Field(..., description="The unique ID of the Repository")
    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
