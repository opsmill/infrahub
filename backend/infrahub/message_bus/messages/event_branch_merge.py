from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class EventBranchMerge(InfrahubMessage):
    """Sent when a branch has been merged."""

    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
