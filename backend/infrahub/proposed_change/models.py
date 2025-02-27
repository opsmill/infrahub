from pydantic import BaseModel, ConfigDict, Field

from infrahub.context import InfrahubContext
from infrahub.message_bus.messages.proposed_change.base_with_diff import BaseProposedChangeWithDiffMessage
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeBranchDiff


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

    context: InfrahubContext = Field(..., description="The context of the task")
