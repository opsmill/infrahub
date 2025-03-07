from typing import Any

from pydantic import Field, computed_field

from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import MutationAction
from infrahub.message_bus import InfrahubMessage

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class NodeMutatedEvent(InfrahubEvent):
    """Event generated when a node has been mutated"""

    kind: str = Field(..., description="The type of object modified")
    node_id: str = Field(..., description="The ID of the mutated node")
    action: MutationAction = Field(..., description="The action taken on the node")
    data: NodeChangelog = Field(..., description="Data on modified object")
    fields: list[str] = Field(default_factory=list, description="Fields provided in the mutation")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        for attribute in self.data.attributes.values():
            related.append(
                {
                    "prefect.resource.id": f"infrahub.node.{self.node_id}",
                    "prefect.resource.role": "infrahub.node.field_update",
                    "infrahub.attribute.name": attribute.name,
                    "infrahub.attribute.value": "NULL" if attribute.value is None else str(attribute.value),
                    "infrahub.attribute.kind": attribute.kind,
                    "infrahub.attribute.value_previous": "NULL"
                    if attribute.value_previous is None
                    else str(attribute.value_previous),
                    # Mypy doesn't understand that .value_update_status is a @computed_attribute
                    "infrahub.attribute.action": attribute.value_update_status.value,  # type: ignore[attr-defined]
                }
            )
        if self.data.parent:
            related.append(
                {
                    "prefect.resource.id": self.data.parent.node_id,
                    "prefect.resource.role": "infrahub.node.parent",
                    "infrahub.parent.kind": self.data.parent.node_kind,
                    "infrahub.parent.id": self.data.parent.node_id,
                }
            )

        related.append(
            {
                "prefect.resource.id": self.node_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": self.kind,
            }
        )

        for related_node in self.data.get_related_nodes():
            related.append(
                {
                    "prefect.resource.id": related_node.node_id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": related_node.node_kind,
                }
            )

        return related

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.node.{self.action.value}"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.node.root_id": self.data.root_node_id,
            "infrahub.branch.name": self.meta.context.branch.name,
        }

    def get_payload(self) -> dict[str, Any]:
        return {"data": self.data.model_dump(), "fields": self.fields}

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
