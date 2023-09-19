from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class CheckRepositoryCheckDefinition(InfrahubBaseMessage):
    """Runs a check as defined within a CoreCheckDefinition within a repository."""

    # validator_id: str = Field(..., description="The id of the validator associated with this check")
    commit: str = Field(..., description="The commit to target")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    file_path: str = Field(..., description="The path and filename of the check")
    class_name: str = Field(..., description="The name of the class containing the check")
