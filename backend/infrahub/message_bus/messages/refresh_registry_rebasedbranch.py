from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RefreshRegistryRebasedBranch(InfrahubMessage):
    """Sent to refresh a rebased branch within the local registry."""

    branch: str = Field(..., description="The branch that was rebased")
