from pydantic import Field

from infrahub.core.ipam.model import IpamNodeDetails
from infrahub.message_bus import InfrahubMessage


class EventBranchRebased(InfrahubMessage):
    """Sent when a branch has been rebased."""

    branch: str = Field(..., description="The branch that was rebased")
    ipam_node_details: list[IpamNodeDetails] = Field(default_factory=list, description="Details for changed IP nodes")
