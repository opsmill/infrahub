from pydantic import ConfigDict, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeBranchDiff


class RequestRepositoryUserChecks(InfrahubMessage):
    """Sent to trigger the user defined checks on a repository."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository: str = Field(..., description="The unique ID of the Repository")
    source_branch: str = Field(..., description="The source branch")
    source_branch_data_only: bool = Field(..., description="Indicates if the source branch is a data only branch")
    target_branch: str = Field(..., description="The target branch")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
