from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class RequestProposedChangeRepositoryChecks(InfrahubMessage):
    """Sent when a proposed change is created to trigger additional checks"""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
