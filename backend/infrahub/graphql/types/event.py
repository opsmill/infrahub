from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, DateTime, Field, Int, Interface, List, NonNull, ObjectType, String
from graphene.types.generic import GenericScalar

from .common import RelatedNode
from .enums import DiffAction

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


class InfrahubMutatedAttribute(ObjectType):
    name = String(required=True)
    action = DiffAction(required=True)
    value = String(required=False)
    kind = String(required=True)
    value_previous = String(required=False)


class EventNodeInterface(Interface):
    id = String(required=True)
    event = String(required=True)
    branch = String(required=False)
    account_id = String(required=False)
    occurred_at = DateTime(required=True)
    level = Int(required=True)
    primary_node = Field(RelatedNode, required=False)
    related_nodes = List(NonNull(RelatedNode), required=True)
    has_children = Boolean(required=True)
    parent_id = String(required=False)

    @classmethod
    def resolve_type(
        cls,
        instance: dict[str, Any],
        info: GraphQLResolveInfo,  # noqa: ARG003
    ) -> type[ObjectType]:
        if "event" in instance:
            return EVENT_TYPES.get(instance["event"], StandardEvent)
        return StandardEvent


class EventNodes(ObjectType):
    node = Field(EventNodeInterface)


# ---------------------------------------
# Branch events
# ---------------------------------------
class BranchCreatedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


class BranchRebasedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


class BranchDeletedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


# ---------------------------------------
# Node/Object events
# ---------------------------------------
class NodeMutatedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)
    attributes = Field(List(of_type=NonNull(InfrahubMutatedAttribute), required=True), required=True)


class StandardEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


EVENT_TYPES: dict[str, type[ObjectType]] = {
    "infrahub.node.created": NodeMutatedEvent,
    "infrahub.node.updated": NodeMutatedEvent,
    "infrahub.node.deleted": NodeMutatedEvent,
    "infrahub.branch.created": BranchCreatedEvent,
    "infrahub.branch.rebased": BranchRebasedEvent,
    "infrahub.branch.deleted": BranchDeletedEvent,
    "undefined": StandardEvent,
}
