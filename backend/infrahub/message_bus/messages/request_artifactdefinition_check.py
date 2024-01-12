from typing import List

from pydantic.v1 import Field

from infrahub.message_bus import InfrahubMessage


class RequestArtifactDefinitionCheck(InfrahubMessage):
    """Sent to validate the generation of artifacts in relation to a proposed change."""

    artifact_definition: str = Field(..., description="The unique ID of the Artifact Definition")
    proposed_change: str = Field(..., description="The unique ID of the Proposed Change")
    source_branch: str = Field(..., description="The source branch")
    source_branch_is_data_only: bool = Field(..., description="Indicates if the source branch is a data only branch")
    target_branch: str = Field(..., description="The target branch")
    impacted_artifacts: List[str] = Field(..., description="List of artifacts with changes within the proposed change")
