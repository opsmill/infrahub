from pydantic import Field

from infrahub.core.ipam.model import IpamNodeDetails
from infrahub.message_bus import InfrahubMessage


class TriggerIpamReconciliation(InfrahubMessage):
    """Sent after a branch has been merged/rebased to reconcile changed IP Prefix and Address nodes"""

    branch: str = Field(..., description="The updated branch")
    ipam_node_details: list[IpamNodeDetails] = Field(..., description="Details for changed IP nodes")
