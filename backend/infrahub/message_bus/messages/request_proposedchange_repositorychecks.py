from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestProposedChangeRepositoryChecks(InfrahubBaseMessage):
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
