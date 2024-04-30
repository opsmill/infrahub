from pydantic import Field

from infrahub.core.ipam.model import IpamNodeDetails
from infrahub.message_bus import InfrahubMessage


class EventBranchMerge(InfrahubMessage):
    """Sent when a branch has been merged."""

    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
    ipam_node_details: list[IpamNodeDetails] = Field(default_factory=list, description="Details for changed IP nodes")
