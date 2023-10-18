from pydantic import Field

from infrahub.message_bus import InfrahubBaseMessage


class TriggerArtifactDefinitionGenerate(InfrahubBaseMessage):
    """Sent after a branch has been merged to start the regeneration of artifacts"""

    branch: str = Field(..., description="The impacted branch")
