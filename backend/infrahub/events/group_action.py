from typing import ClassVar

from pydantic import Field

from infrahub.core.constants import InfrahubKind, MutationAction

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

        if self.kind == InfrahubKind.GRAPHQLQUERYGROUP:
            # Temporary workaround to avoid too large payloads for the related field
            return related

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

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.node.root_id": self.node_id,
        }


class GroupMemberAddedEvent(GroupMutatedEvent):
    """Event generated when a one or more members have been added to a group"""

    action: MutationAction = MutationAction.CREATED
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.member_added"
    infrahub_node_kind_event: ClassVar[bool] = True


class GroupMemberRemovedEvent(GroupMutatedEvent):
    """Event generated when a one or more members have been removed to a group"""

    action: MutationAction = MutationAction.DELETED
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.member_removed"
    infrahub_node_kind_event: ClassVar[bool] = True
