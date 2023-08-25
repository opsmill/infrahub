from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestProposedChangeDataIntegrity(InfrahubBaseMessage):
    """Sent trigger data integrity checks for a proposed change"""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
