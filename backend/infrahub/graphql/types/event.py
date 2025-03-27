from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, DateTime, Field, InputObjectType, Int, Interface, List, NonNull, ObjectType, String
from graphene.types.generic import GenericScalar

from infrahub import events

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


class InfrahubMutatedRelationship(ObjectType):
    name = String(required=True)
    action = DiffAction(required=True)
    peer = Field(RelatedNode, required=True)


class EventNodeInterface(Interface):
    id = String(required=True, description="The ID of the event.")
    event = String(required=True, description="The name of the event.")
    branch = String(required=False, description="The branch where the event occurred.")
    account_id = String(required=False, description="The account ID that triggered the event.")
    occurred_at = DateTime(required=True, description="The timestamp when the event occurred.")
    level = Int(
        required=True,
        description="The level of the event 0 is a root level event, the child events will have 1 and grand children 2.",
    )
    primary_node = Field(
        RelatedNode, required=False, description="The primary Infrahub node this event is associated with."
    )
    related_nodes = List(
        NonNull(RelatedNode), required=True, description="Related Infrahub nodes this event is associated with."
    )
    has_children = Boolean(
        required=True, description="Indicates if the event is expected to have child events under it"
    )
    parent_id = String(required=False, description="The event ID of the direct parent to this event.")

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


class BranchEventTypeFilter(InputObjectType):
    branches = List(NonNull(String), required=True, description="Name of impacted branches")


class EventTypeFilter(InputObjectType):
    branch_merged = Field(
        BranchEventTypeFilter, required=False, description="Filters specific to infrahub.branch.merged events"
    )
    branch_rebased = Field(
        BranchEventTypeFilter, required=False, description="Filters specific to infrahub.branch.rebased events"
    )


# ---------------------------------------
# Branch events
# ---------------------------------------
class BranchCreatedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    created_branch = String(required=True, description="The name of the branch that was created")
    payload = Field(GenericScalar, required=True)


class BranchMergedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    source_branch = String(required=True, description="The name of the branch that was merged into the default branch")


class BranchRebasedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    rebased_branch = String(
        required=True, description="The name of the branch that was rebased and aligned with the default branch"
    )
    payload = Field(GenericScalar, required=True)


class BranchDeletedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    deleted_branch = String(required=True, description="The name of the branch that was deleted")
    payload = Field(GenericScalar, required=True)


# ---------------------------------------
# Node/Object events
# ---------------------------------------
class NodeMutatedEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)
    attributes = Field(List(of_type=NonNull(InfrahubMutatedAttribute), required=True), required=True)
    relationships = Field(List(of_type=NonNull(InfrahubMutatedRelationship), required=True), required=True)


class ArtifactEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    checksum = String(required=True, description="The current checksum of the artifact")
    checksum_previous = String(required=False, description="The previous checksum of the artifact")
    storage_id = String(required=True, description="The current storage_id of the artifact")
    storage_id_previous = String(required=False, description="The previous storage_id of the artifact")
    artifact_definition_id = String(required=True, description="Artifact definition ID")


class GroupEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    members = List(NonNull(RelatedNode), required=True, description="Group members modified in this event")
    ancestors = List(NonNull(RelatedNode), required=True, description="Ancestor groups of this impacted group")


class StandardEvent(ObjectType):
    class Meta:
        interfaces = (EventNodeInterface,)

    payload = Field(GenericScalar, required=True)


EVENT_TYPES: dict[str, type[ObjectType]] = {
    events.ArtifactCreatedEvent.event_name: ArtifactEvent,
    events.ArtifactUpdatedEvent.event_name: ArtifactEvent,
    events.NodeCreatedEvent.event_name: NodeMutatedEvent,
    events.NodeUpdatedEvent.event_name: NodeMutatedEvent,
    events.NodeDeletedEvent.event_name: NodeMutatedEvent,
    events.BranchCreatedEvent.event_name: BranchCreatedEvent,
    events.BranchMergedEvent.event_name: BranchMergedEvent,
    events.BranchRebasedEvent.event_name: BranchRebasedEvent,
    events.BranchDeletedEvent.event_name: BranchDeletedEvent,
    events.GroupMemberAddedEvent.event_name: GroupEvent,
    events.GroupMemberRemovedEvent.event_name: GroupEvent,
    "undefined": StandardEvent,
}
