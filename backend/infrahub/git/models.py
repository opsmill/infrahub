from typing import Optional

from pydantic import BaseModel, Field


class RequestArtifactDefinitionGenerate(BaseModel):
    """Sent to trigger the generation of artifacts for a given branch."""

    artifact_definition: str = Field(..., description="The unique ID of the Artifact Definition")
    branch: str = Field(..., description="The branch to target")
    limit: list[str] = Field(
        default_factory=list,
        description="List of targets to limit the scope of the generation, if populated only the included artifacts will be regenerated",
    )


class RequestArtifactGenerate(BaseModel):
    """Runs to generate an artifact"""

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


class GitRepositoryAdd(BaseModel):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    created_by: Optional[str] = Field(default=None, description="The user ID of the user that created the repository")
    default_branch_name: Optional[str] = Field(None, description="Default branch for this repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
    internal_status: str = Field(..., description="Administrative status of the repository")


class GitRepositoryAddReadOnly(BaseModel):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    ref: str = Field(..., description="Ref to track on the external repository")
    created_by: Optional[str] = Field(default=None, description="The user ID of the user that created the repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
    internal_status: str = Field(..., description="Internal status of the repository")


class GitRepositoryPullReadOnly(BaseModel):
    """Update a read-only repository to the latest commit for its ref"""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    ref: Optional[str] = Field(None, description="Ref to track on the external repository")
    commit: Optional[str] = Field(None, description="Specific commit to pull")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Infrahub branch on which to sync the remote repository")


class GitRepositoryMerge(BaseModel):
    """Merge one branch into another."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    internal_status: str = Field(..., description="Administrative status of the repository")
    source_branch: str = Field(..., description="The source branch")
    destination_branch: str = Field(..., description="The destination branch")
    destination_branch_id: str = Field(..., description="The ID of the destination branch")
    default_branch: str = Field(..., description="The default branch in Git")


class GitRepositoryImportObjects(BaseModel):
    """Re run import job against an existing commit."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    commit: str = Field(..., description="Specific commit to pull")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")


class GitDiffNamesOnly(BaseModel):
    """Request a list of modified files between two commits."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    first_commit: str = Field(..., description="The first commit")
    second_commit: Optional[str] = Field(None, description="The second commit")


class GitDiffNamesOnlyResponse(BaseModel):
    files_added: list[str] = Field(..., description="Files added")
    files_changed: list[str] = Field(..., description="Files changed")
    files_removed: list[str] = Field(..., description="Files removed")
