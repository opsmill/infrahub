from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class CheckRepositoryCheckDefinition(InfrahubMessage):
    """Triggers user defined checks to run based on a Check Definition."""

    check_definition_id: str = Field(..., description="The unique ID of the check definition")
    commit: str = Field(..., description="The commit to target")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    file_path: str = Field(..., description="The path and filename of the check")
    class_name: str = Field(..., description="The name of the class containing the check")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
