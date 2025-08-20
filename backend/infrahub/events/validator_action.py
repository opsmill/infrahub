from typing import ClassVar

from pydantic import Field

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


class ValidatorStartedEvent(ValidatorEvent):
    """Event generated when an validator within a pipeline has started."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.validator.started"
    infrahub_node_kind_event: ClassVar[bool] = True


class ValidatorPassedEvent(ValidatorEvent):
    """Event generated when an validator within a pipeline has completed successfully."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.validator.passed"
    infrahub_node_kind_event: ClassVar[bool] = True


class ValidatorFailedEvent(ValidatorEvent):
    """Event generated when an validator within a pipeline has completed successfully."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.validator.failed"
    infrahub_node_kind_event: ClassVar[bool] = True
