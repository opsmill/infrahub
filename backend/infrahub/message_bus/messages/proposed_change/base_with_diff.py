from pydantic import ConfigDict, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeBranchDiff


class BaseProposedChangeWithDiffMessage(InfrahubMessage):
    """Sent trigger the refresh of artifacts that are impacted by the proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch of the proposed change")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The destination branch of the proposed change")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
