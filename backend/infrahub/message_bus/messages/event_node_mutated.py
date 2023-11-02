from typing import Any, Dict

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class EventNodeMutated(InfrahubMessage):
    """Sent when a node has been mutated"""

    branch: str = Field(..., description="The branch that was created")
    kind: str = Field(..., description="The type of object modified")
    node_id: str = Field(..., description="The ID of the mutated node")
    action: str = Field(..., description="The action taken on the node")
    data: Dict[str, Any] = Field(..., description="Data on modified object")
