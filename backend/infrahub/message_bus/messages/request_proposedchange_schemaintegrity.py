from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestProposedChangeSchemaIntegrity(InfrahubBaseMessage):
    """Sent trigger schema integrity checks for a proposed change"""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
