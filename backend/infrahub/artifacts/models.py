from pydantic import BaseModel, Field

from infrahub.context import InfrahubContext


class CheckArtifactCreate(BaseModel):
    """Runs a check to verify the creation of an artifact."""

    artifact_name: str = Field(..., description="Name of the artifact")
    artifact_definition: str = Field(..., description="The the ID of the artifact definition")
    commit: str = Field(..., description="The commit to target")
    content_type: str = Field(..., description="Content type of the artifact")
    transform_type: str = Field(..., description="The type of transform associated with this artifact")
    transform_location: str = Field(..., description="The transforms location within the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    repository_kind: str = Field(..., description="The kind of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    target_id: str = Field(..., description="The ID of the target object for this artifact")
    target_kind: str = Field(..., description="The kind of the target object for this artifact")
    target_name: str = Field(..., description="Name of the artifact target")
    artifact_id: str | None = Field(default=None, description="The id of the artifact if it previously existed")
    query: str = Field(..., description="The name of the query to use when collecting data")
    timeout: int = Field(..., description="Timeout for requests used to generate this artifact")
    variables: dict = Field(..., description="Input variables when generating the artifact")
    validator_id: str = Field(..., description="The ID of the validator")
    context: InfrahubContext = Field(..., description="The context of the task")
