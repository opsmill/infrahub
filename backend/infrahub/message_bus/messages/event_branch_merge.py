from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class EventBranchMerge(InfrahubBaseMessage):
    """Sent when a branch has been merged."""

    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
