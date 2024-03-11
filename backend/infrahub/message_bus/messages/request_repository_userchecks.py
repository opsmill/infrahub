from pydantic import ConfigDict, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeBranchDiff


class RequestRepositoryUserChecks(InfrahubMessage):
    """Sent to trigger the user defined checks on a repository."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository: str = Field(..., description="The unique ID of the Repository")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    target_branch: str = Field(..., description="The target branch")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
