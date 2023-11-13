from typing import List

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestArtifactDefinitionGenerate(InfrahubMessage):
    """Sent to trigger the generation of artifacts for a given branch."""

    artifact_definition: str = Field(..., description="The unique ID of the Artifact Definition")
    branch: str = Field(..., description="The branch to target")
    limit: List[str] = Field(
        default_factory=list,
        description="List of targets to limit the scope of the generation, if populated only the included artifacts will be regenerated",
    )
