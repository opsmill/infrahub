from pydantic import BaseModel, Field

from infrahub.context import InfrahubContext


class BranchMergePostProcessModel(BaseModel):
    """Sent when a branch has been merged."""

    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")

    context: InfrahubContext = Field(..., description="The context of the event")
