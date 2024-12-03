from pydantic import Field

from infrahub.message_bus.messages.proposed_change.base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeDataIntegrity(BaseProposedChangeWithDiffMessage):
    """Sent trigger data integrity checks for a proposed change"""


class RequestProposedChangeRunGenerators(BaseProposedChangeWithDiffMessage):
    """Sent trigger the generators that are impacted by the proposed change to run."""

    refresh_artifacts: bool = Field(..., description="Whether to regenerate artifacts after the generators are run")
    do_repository_checks: bool = Field(
        ..., description="Whether to run repository and user checks after the generators are run"
    )


class RequestProposedChangeRepositoryChecks(BaseProposedChangeWithDiffMessage):
    """Sent when a proposed change is created to trigger additional checks"""


class RequestProposedChangeSchemaIntegrity(BaseProposedChangeWithDiffMessage):
    """Sent trigger schema integrity checks for a proposed change"""


class RequestProposedChangeUserTests(BaseProposedChangeWithDiffMessage):
    """Sent trigger to run tests (smoke, units, integrations) for a proposed change."""
