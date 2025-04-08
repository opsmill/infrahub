from typing import ClassVar

from pydantic import Field

from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.constants import DiffAction, InfrahubKind, MutationAction

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class NodeMutatedEvent(InfrahubEvent):
    """Event generated when a node has been mutated"""

    kind: str = Field(..., description="The type of object modified")
    node_id: str = Field(..., description="The ID of the mutated node")
    action: MutationAction = Field(..., description="The action taken on the node")
    changelog: NodeChangelog = Field(..., description="Data on modified object")
    fields: list[str] = Field(default_factory=list, description="Fields provided in the mutation")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        if self.kind == InfrahubKind.GRAPHQLQUERYGROUP:
            # Temporary workaround to avoid too large payloads for the related field
            return related

        for attribute in self.changelog.attributes.values():
            related.append(
                {
                    "prefect.resource.id": f"infrahub.node.{self.node_id}",
                    "prefect.resource.role": "infrahub.node.attribute_update",
                    "infrahub.field.name": attribute.name,
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

        for relationship in self.changelog.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog) and not relationship.is_empty:
                if relationship.peer_id and relationship.peer_kind:
                    related.append(
                        self._format_relationship_resource(
                            relationship_name=relationship.name,
                            peer_id=relationship.peer_id,
                            peer_kind=relationship.peer_kind,
                            action=DiffAction.ADDED,
                        )
                    )

                if relationship.peer_id_previous and relationship.peer_kind_previous:
                    related.append(
                        self._format_relationship_resource(
                            relationship_name=relationship.name,
                            peer_id=relationship.peer_id_previous,
                            peer_kind=relationship.peer_kind_previous,
                            action=DiffAction.REMOVED,
                        )
                    )

            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                for peer in relationship.peers:
                    if peer.peer_status in [DiffAction.ADDED, DiffAction.REMOVED]:
                        related.append(
                            self._format_relationship_resource(
                                relationship_name=relationship.name,
                                peer_id=peer.peer_id,
                                peer_kind=peer.peer_kind,
                                action=peer.peer_status,
                            )
                        )

        if self.changelog.parent:
            related.append(
                {
                    "prefect.resource.id": self.changelog.parent.node_id,
                    "prefect.resource.role": "infrahub.node.parent",
                    "infrahub.parent.kind": self.changelog.parent.node_kind,
                    "infrahub.parent.id": self.changelog.parent.node_id,
                }
            )

        related.append(
            {
                "prefect.resource.id": self.node_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": self.kind,
            }
        )

        for related_node in self.changelog.get_related_nodes():
            related.append(
                {
                    "prefect.resource.id": related_node.node_id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": related_node.node_kind,
                }
            )

        return related

    def _format_relationship_resource(
        self, relationship_name: str, peer_id: str, peer_kind: str, action: DiffAction
    ) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "prefect.resource.role": "infrahub.node.relationship_update",
            "infrahub.field.name": relationship_name,
            "infrahub.relationship.name": relationship_name,
            "infrahub.relationship.peer_status": action.value,
            "infrahub.relationship.peer_id": peer_id,
            "infrahub.relationship.peer_kind": peer_kind,
        }

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.node.root_id": self.changelog.root_node_id,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class NodeCreatedEvent(NodeMutatedEvent):
    """Event generated when a node has been created"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.node.created"
    action: MutationAction = MutationAction.CREATED
    infrahub_node_kind_event: ClassVar[bool] = True


class NodeUpdatedEvent(NodeMutatedEvent):
    """Event generated when a node has been updated"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.node.updated"
    action: MutationAction = MutationAction.UPDATED
    infrahub_node_kind_event: ClassVar[bool] = True


class NodeDeletedEvent(NodeMutatedEvent):
    """Event generated when a node has been deleted"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.node.deleted"
    action: MutationAction = MutationAction.DELETED
    infrahub_node_kind_event: ClassVar[bool] = True


def get_node_event(action: MutationAction) -> type[NodeDeletedEvent] | type[NodeUpdatedEvent] | type[NodeCreatedEvent]:
    if action == MutationAction.CREATED:
        return NodeCreatedEvent
    if action == MutationAction.UPDATED:
        return NodeUpdatedEvent
    if action == MutationAction.DELETED:
        return NodeDeletedEvent
    raise ValueError(f"Invalid action: {action}")
