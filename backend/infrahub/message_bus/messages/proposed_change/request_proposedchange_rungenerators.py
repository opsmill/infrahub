from pydantic import Field

from .base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeRunGenerators(BaseProposedChangeWithDiffMessage):
    """Sent trigger the generators that are impacted by the proposed change to run."""

    refresh_artifacts: bool = Field(..., description="Whether to regenerate artifacts after the generators are run")
    do_repository_checks: bool = Field(
        ..., description="Whether to run repository and user checks after the generators are run"
    )
