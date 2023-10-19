from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestArtifactDefinitionCheck(InfrahubBaseMessage):
    """Sent to validate the generation of artifacts in relation to a proposed change."""

    artifact_definition: str = Field(..., description="The unique ID of the Artifact Definition")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    target_branch: str = Field(..., description="The target branch")
