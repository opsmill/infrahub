from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class EventBranchRebased(InfrahubMessage):
    """Sent when a branch has been rebased."""

    branch: str = Field(..., description="The branch that was rebased")
