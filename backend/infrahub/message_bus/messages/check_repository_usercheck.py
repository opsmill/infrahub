from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class CheckRepositoryUserCheck(InfrahubMessage):
    """Runs a check as defined within a CoreCheckDefinition within a repository."""

    validator_id: str = Field(..., description="The id of the validator associated with this check")
    validator_execution_id: str = Field(..., description="The id of current execution of the associated validator")
    check_execution_id: str = Field(..., description="The unique ID for the current execution of this check")
    check_definition_id: str = Field(..., description="The unique ID of the check definition")
    commit: str = Field(..., description="The commit to target")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    file_path: str = Field(..., description="The path and filename of the check")
    class_name: str = Field(..., description="The name of the class containing the check")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    variables: dict = Field(default_factory=dict, description="Input variables when running the check")
    name: str = Field(..., description="The name of the check")
