from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestProposedChangeRefreshArtifacts(InfrahubMessage):
    """Sent trigger the refresh of artifacts that are impacted by the proposed change."""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
