from pydantic import Field, computed_field

from infrahub.message_bus import InfrahubMessage

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class ValidatorEvent(InfrahubEvent):
    """Event generated when an validator within a pipeline has started."""

    node_id: str = Field(..., description="The ID of the validator")
    kind: str = Field(..., description="The kind of the validator")
    proposed_change_id: str = Field(..., description="The ID of the proposed change")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": self.node_id,
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.branch.name": self.meta.context.branch.name,
        }

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.proposed_change_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": "CoreProposedChange",
            }
        )

        return related

    def get_messages(self) -> list[InfrahubMessage]:
        return []


class ValidatorStartedEvent(ValidatorEvent):
    """Event generated when an validator within a pipeline has started."""

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.validator.started"


class ValidatorPassedEvent(ValidatorEvent):
    """Event generated when an validator within a pipeline has completed successfully."""

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.validator.passed"


class ValidatorFailedEvent(ValidatorEvent):
    """Event generated when an validator within a pipeline has completed successfully."""

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.validator.failed"
