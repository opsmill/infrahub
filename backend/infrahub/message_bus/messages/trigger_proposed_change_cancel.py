from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class TriggerProposedChangeCancel(InfrahubMessage):
    """Triggers request to cancel any open or closed proposed changes for a given branch"""

    branch: str = Field(..., description="The impacted branch")
