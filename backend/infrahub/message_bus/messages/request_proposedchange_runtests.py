from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeBranchDiff


class RequestProposedChangeRunTests(InfrahubMessage):
    """Sent trigger to run tests (smoke, units, integrations) for a proposed change."""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch of the proposed change")
    source_branch_data_only: bool = Field(..., description="Indicates if the source branch is a data only branch")
    destination_branch: str = Field(..., description="The destination branch of the proposed change")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
