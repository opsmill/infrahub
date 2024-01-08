from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class TriggerArtifactDefinitionGenerate(InfrahubMessage):
    """Sent after a branch has been merged to start the regeneration of artifacts"""

    branch: str = Field(..., description="The impacted branch")
