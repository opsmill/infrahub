from pydantic import BaseModel, ConfigDict, Field

from infrahub.context import InfrahubContext
from infrahub.message_bus.types import ProposedChangeBranchDiff


class RequestArtifactDefinitionGenerate(BaseModel):
    """Sent to trigger the generation of artifacts for a given branch."""

    artifact_definition_id: str = Field(..., description="The unique ID of the Artifact Definition")
    artifact_definition_name: str = Field(..., description="The name of the Artifact Definition")
    branch: str = Field(..., description="The branch to target")
    limit: list[str] = Field(
        default_factory=list,
        description="List of targets to limit the scope of the generation, if populated only the included artifacts will be regenerated",
    )


class RequestArtifactGenerate(BaseModel):
    """Runs to generate an artifact"""

    artifact_name: str = Field(..., description="Name of the artifact")
    artifact_definition: str = Field(..., description="The ID of the artifact definition")
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
    context: InfrahubContext = Field(..., description="The context of the task")


class GitRepositoryAdd(BaseModel):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    created_by: str | None = Field(default=None, description="The user ID of the user that created the repository")
    default_branch_name: str | None = Field(None, description="Default branch for this repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
    internal_status: str = Field(..., description="Administrative status of the repository")


class GitRepositoryAddReadOnly(BaseModel):
    """Clone and sync an external repository after creation."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    ref: str = Field(..., description="Ref to track on the external repository")
    created_by: str | None = Field(default=None, description="The user ID of the user that created the repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
    internal_status: str = Field(..., description="Internal status of the repository")


class GitRepositoryPullReadOnly(BaseModel):
    """Update a read-only repository to the latest commit for its ref"""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    ref: str | None = Field(None, description="Ref to track on the external repository")
    commit: str | None = Field(None, description="Specific commit to pull")
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
    second_commit: str | None = Field(None, description="The second commit")


class GitDiffNamesOnlyResponse(BaseModel):
    files_added: list[str] = Field(..., description="Files added")
    files_changed: list[str] = Field(..., description="Files changed")
    files_removed: list[str] = Field(..., description="Files removed")


class UserCheckDefinitionData(BaseModel):
    """Triggers user defined checks to run based on a Check Definition."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    check_definition_id: str = Field(..., description="The unique ID of the check definition")
    commit: str = Field(..., description="The commit to target")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    file_path: str = Field(..., description="The path and filename of the check")
    class_name: str = Field(..., description="The name of the class containing the check")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")


class UserCheckData(BaseModel):
    """Runs a check as defined within a CoreCheckDefinition within a repository."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
    timeout: int = Field(..., description="The timeout for the check")


class TriggerRepositoryUserChecks(BaseModel):
    """Sent to trigger the user defined checks on a repository."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    target_branch: str = Field(..., description="The target branch")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")


class TriggerRepositoryInternalChecks(BaseModel):
    """Sent to trigger the checks for a repository to be executed."""

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository: str = Field(..., description="The unique ID of the Repository")
    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")


class CheckRepositoryMergeConflicts(BaseModel):
    """Runs a check to validate if there are merge conflicts for a proposed change between two branches."""

    validator_id: str = Field(..., description="The id of the validator associated with this check")
    validator_execution_id: str = Field(..., description="The id of current execution of the associated validator")
    check_execution_id: str = Field(..., description="The unique ID for the current execution of this check")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")


class RepositoryBranchInfo(BaseModel):
    internal_status: str


class RepositoryData(BaseModel):
    repository_id: str = Field(..., description="Id of the repository")
    repository_name: str = Field(..., description="Name of the repository")
    branches: dict[str, str] = Field(
        ...,
        description="Dictionary with the name of the branch as the key and the active commit id as the value",
    )

    branch_info: dict[str, RepositoryBranchInfo] = Field(default_factory=dict)
