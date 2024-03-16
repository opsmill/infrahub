from pydantic import ConfigDict, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeBranchDiff


class RequestArtifactDefinitionCheck(InfrahubMessage):
    """Sent to validate the generation of artifacts in relation to a proposed change."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    artifact_definition: ProposedChangeArtifactDefinition = Field(..., description="The Artifact Definition")
    branch_diff: ProposedChangeBranchDiff = Field(..., description="The calculated diff between the two branches")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The target branch")
