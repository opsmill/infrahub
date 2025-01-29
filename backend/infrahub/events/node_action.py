from typing import Any

from pydantic import Field, ValidationInfo, field_validator

from infrahub.core.constants import MutationAction
from infrahub.message_bus import InfrahubMessage

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class NodeMutatedEvent(InfrahubEvent):
    """Event generated when a node has been mutated"""

    event_name: str = Field(default="infrahub.node.unknown", description="The name of the event")

    kind: str = Field(..., description="The type of object modified")
    node_id: str = Field(..., description="The ID of the mutated node")
    action: MutationAction = Field(..., description="The action taken on the node")
    data: dict[str, Any] = Field(..., description="Data on modified object")
    fields: list[str] = Field(default_factory=list, description="Fields provided in the mutation")

    @field_validator("event_name", mode="after")
    @classmethod
    def updaate_event_name(cls, value: str, info: ValidationInfo) -> str:  # noqa: ARG003
        action: MutationAction = info.data["action"]
        return f"{EVENT_NAMESPACE}.node.{action.value}"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
        }

    def get_payload(self) -> dict[str, Any]:
        return {"data": self.data, "fields": self.fields}

    def get_messages(self) -> list[InfrahubMessage]:
        return [
            # EventNodeMutated(
            #     branch=self.branch,
            #     kind=self.kind,
            #     node_id=self.node_id,
            #     action=self.action.value,
            #     data=self.data,
            #     meta=self.get_message_meta(),
            # )
        ]


class NodeCreatedEvent(NodeMutatedEvent):
    action: MutationAction = MutationAction.CREATED


class NodeUpdatedEvent(NodeMutatedEvent):
    action: MutationAction = MutationAction.UPDATED


class NodeDeletedEvent(NodeMutatedEvent):
    action: MutationAction = MutationAction.DELETED
