from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestProposedChangeCancel(InfrahubMessage):
    """Cancel the proposed change"""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
