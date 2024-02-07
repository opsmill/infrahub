from pydantic import ConfigDict, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeBranchDiff


class RequestProposedChangeRepositoryChecks(InfrahubMessage):
    """Sent when a proposed change is created to trigger additional checks"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch of the proposed change")
    source_branch_data_only: bool = Field(..., description="Indicates if the source branch is a data only branch")
    destination_branch: str = Field(..., description="The destination branch of the proposed change")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
