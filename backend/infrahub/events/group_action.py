from typing import Any

from pydantic import Field, computed_field

from infrahub.core.constants import MutationAction
from infrahub.message_bus import InfrahubMessage

from .constants import EVENT_NAMESPACE
from .models import EventNode, InfrahubEvent


class GroupMutatedEvent(InfrahubEvent):
    """Event generated when a node has been mutated"""

    kind: str = Field(..., description="The type of updated group")
    node_id: str = Field(..., description="The ID of the updated group")
    action: MutationAction = Field(..., description="The action taken on the node")
    members: list[EventNode] = Field(default_factory=list, description="Updated members during this event.")
    ancestors: list[EventNode] = Field(
        default_factory=list, description="A list of groups that are ancestors of this group."
    )

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.node_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": self.kind,
            }
        )
        related.append(
            {
                "prefect.resource.id": self.node_id,
                "prefect.resource.role": "infrahub.group.update",
                "infrahub.node.kind": self.kind,
            }
        )

        for member in self.members:
            related.append(
                {
                    "prefect.resource.id": member.id,
                    "prefect.resource.role": "infrahub.group.member",
                    "infrahub.node.kind": member.kind,
                }
            )
            related.append(
                {
                    "prefect.resource.id": member.id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": member.kind,
                }
            )

        for ancestor in self.ancestors:
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.group.ancestor",
                    "infrahub.node.kind": ancestor.kind,
                }
            )
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": ancestor.kind,
                }
            )
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.group.update",
                    "infrahub.node.kind": ancestor.kind,
                }
            )

        return related

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.group.{self.action.value}"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.node.root_id": self.node_id,
        }

    def get_payload(self) -> dict[str, Any]:
        return {
            "ancestors": [ancestor.model_dump() for ancestor in self.ancestors],
            "members": [member.model_dump() for member in self.members],
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return []


class GroupMemberAddedEvent(GroupMutatedEvent):
    action: MutationAction = MutationAction.CREATED

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.group.member_added"


class GroupMemberRemovedEvent(GroupMutatedEvent):
    action: MutationAction = MutationAction.DELETED

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.group.member_removed"
