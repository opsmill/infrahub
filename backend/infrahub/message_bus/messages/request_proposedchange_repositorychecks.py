from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestProposedChangeRepositoryChecks(InfrahubBaseMessage):
    """Sent when a proposed change is created to trigger additional checks"""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
