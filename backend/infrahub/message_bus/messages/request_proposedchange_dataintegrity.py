from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class RequestProposedChangeDataIntegrity(InfrahubMessage):
    """Sent trigger data integrity checks for a proposed change"""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
