from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class RequestArtifactDefinitionGenerate(InfrahubBaseMessage):
    """Sent to trigger the generation of artifacts for a given branch."""

    artifact_definition: str = Field(..., description="The unique ID of the Artifact Definition")
    branch: str = Field(..., description="The branch to target")
