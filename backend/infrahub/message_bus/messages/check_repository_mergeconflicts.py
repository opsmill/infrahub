from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class CheckRepositoryMergeConflicts(InfrahubMessage):
    """Runs a check to validate if there are merge conflicts for a proposed change between two branches."""

    validator_id: str = Field(..., description="The id of the validator associated with this check")
    validator_execution_id: str = Field(..., description="The id of current execution of the associated validator")
    check_execution_id: str = Field(..., description="The unique ID for the current execution of this check")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
