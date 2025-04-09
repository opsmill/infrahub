import uuid

from pydantic import Field

from infrahub.context import InfrahubContext
from infrahub.core.constants import CheckType
from infrahub.message_bus import InfrahubMessage


class RequestProposedChangePipeline(InfrahubMessage):
    """Sent request the start of a pipeline connected to a proposed change."""

    proposed_change: str = Field(..., description="The unique ID of the proposed change")
    source_branch: str = Field(..., description="The source branch of the proposed change")
    source_branch_sync_with_git: bool = Field(..., description="Indicates if the source branch should sync with git")
    destination_branch: str = Field(..., description="The destination branch of the proposed change")
    check_type: CheckType = Field(
        default=CheckType.ALL, description="Can be used to restrict the pipeline to a specific type of job"
    )
    context: InfrahubContext = Field(..., description="The context of the task")
    pipeline_id: uuid.UUID = Field(
        default_factory=uuid.uuid4, description="The unique ID of the execution of this pipeline"
    )
