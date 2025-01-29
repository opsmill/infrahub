from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Interface, ObjectType, String
from graphene.types.generic import GenericScalar

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


class EventNodeInterface(Interface):
    id = String(required=True)
    event = String(required=True)
    branch = String(required=False)

    @classmethod
    def resolve_type(cls, instance: dict[str, Any], info: GraphQLResolveInfo) -> ObjectType:  # noqa: ARG003
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
class NodeAddedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


class StandardEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


EVENT_TYPES: dict[str, type[ObjectType]] = {
    "infrahub.node.added": NodeAddedEvent,
    "infrahub.branch.created": BranchCreatedEvent,
    "infrahub.branch.rebased": BranchRebasedEvent,
    "infrahub.branch.deleted": BranchDeletedEvent,
    "undefined": StandardEvent,
}
