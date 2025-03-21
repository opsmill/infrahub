from pydantic import Field

from infrahub.context import InfrahubContext

from .base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeRefreshArtifacts(BaseProposedChangeWithDiffMessage):
    """Sent trigger the refresh of artifacts that are impacted by the proposed change."""

    context: InfrahubContext = Field(..., description="The context of the task")
