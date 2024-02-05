from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestProposedChangeRunTests(InfrahubMessage):
    """Sent trigger to run tests (sanity, units, integrations) for a proposed change."""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
