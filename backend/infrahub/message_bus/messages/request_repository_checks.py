from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class RequestRepositoryChecks(InfrahubMessage):
    """Sent to trigger the checks for a repository to be executed."""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository: str = Field(..., description="The unique ID of the Repository")
    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
