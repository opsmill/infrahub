import uuid

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.constants import CheckType
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeBranchDiff


class BaseProposedChangeWithDiffMessage(InfrahubMessage):
    """Sent trigger the refresh of artifacts that are impacted by the proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch of the proposed change")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The destination branch of the proposed change")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")


class RequestProposedChangeDataIntegrity(BaseProposedChangeWithDiffMessage):
    """Sent trigger data integrity checks for a proposed change"""


class RequestProposedChangeRunGenerators(BaseProposedChangeWithDiffMessage):
    """Sent trigger the generators that are impacted by the proposed change to run."""

    refresh_artifacts: bool = Field(..., description="Whether to regenerate artifacts after the generators are run")
    do_repository_checks: bool = Field(
        ..., description="Whether to run repository and user checks after the generators are run"
    )


class RequestProposedChangeRepositoryChecks(BaseProposedChangeWithDiffMessage):
    """Sent when a proposed change is created to trigger additional checks"""


class RequestProposedChangeSchemaIntegrity(BaseProposedChangeWithDiffMessage):
    """Sent trigger schema integrity checks for a proposed change"""


class RequestProposedChangeUserTests(BaseProposedChangeWithDiffMessage):
    """Sent trigger to run tests (smoke, units, integrations) for a proposed change."""


class RequestArtifactDefinitionCheck(BaseModel):
    """Sent to validate the generation of artifacts in relation to a proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    artifact_definition: ProposedChangeArtifactDefinition = Field(..., description="The Artifact Definition")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The target branch")


class RunGeneratorAsCheckModel(BaseModel):
    """A check that runs a generator."""

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator definition")
    generator_instance: str | None = Field(
        default=None, description="The id of the generator instance if it previously existed"
    )
    commit: str = Field(..., description="The commit to target")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    repository_kind: str = Field(..., description="The kind of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    target_id: str = Field(..., description="The ID of the target object for this generator")
    target_name: str = Field(..., description="Name of the generator target")
    query: str = Field(..., description="The name of the query to use when collecting data")
    variables: dict = Field(..., description="Input variables when running the generator")
    validator_id: str = Field(..., description="The ID of the validator")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")


class RequestGeneratorDefinitionCheck(BaseModel):
    """Sent to trigger Generators to run for a proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator Definition")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The target branch")


class RequestProposedChangePipeline(BaseModel):
    """Sent request the start of a pipeline connected to a proposed change."""

    proposed_change: str = Field(..., description="The unique ID of the proposed change")
    source_branch: str = Field(..., description="The source branch of the proposed change")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The destination branch of the proposed change")
    check_type: CheckType = Field(
        default=CheckType.ALL, description="Can be used to restrict the pipeline to a specific type of job"
    )
    pipeline_id: uuid.UUID = Field(
        default_factory=uuid.uuid4, description="The unique ID of the execution of this pipeline"
    )


class RequestProposedChangeRefreshArtifacts(BaseProposedChangeWithDiffMessage):
    """Sent trigger the refresh of artifacts that are impacted by the proposed change."""
