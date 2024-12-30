from typing import Any

from pydantic import Field

from infrahub.core.constants import MutationAction
from infrahub.message_bus import InfrahubMessage

from .models import InfrahubBranchEvent


class NodeMutatedEvent(InfrahubBranchEvent):
    """Event generated when a node has been mutated"""

    kind: str = Field(..., description="The type of object modified")
    node_id: str = Field(..., description="The ID of the mutated node")
    action: MutationAction = Field(..., description="The action taken on the node")
    data: dict[str, Any] = Field(..., description="Data on modified object")
    fields: list[str] = Field(default_factory=list, description="Fields provided in the mutation")

    def get_name(self) -> str:
        return f"{self.get_event_namespace()}.node.{self.action.value}"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.branch.name": self.branch,
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
