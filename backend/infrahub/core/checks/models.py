from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeBranchDiff


class RequestArtifactDefinitionCheck(BaseModel):
    """Sent to validate the generation of artifacts in relation to a proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    artifact_definition: ProposedChangeArtifactDefinition = Field(..., description="The Artifact Definition")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The target branch")


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
    target_name: str = Field(..., description="Name of the artifact target")
    artifact_id: Optional[str] = Field(default=None, description="The id of the artifact if it previously existed")
    query: str = Field(..., description="The name of the query to use when collecting data")
    timeout: int = Field(..., description="Timeout for requests used to generate this artifact")
    variables: dict = Field(..., description="Input variables when generating the artifact")
    validator_id: str = Field(..., description="The ID of the validator")
