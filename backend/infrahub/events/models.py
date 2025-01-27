from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from infrahub.message_bus import InfrahubMessage, Meta

from .constants import EVENT_NAMESPACE


class EventMeta(BaseModel):
    request_id: str = ""
    account_id: str = ""
    initiator_id: str | None = Field(
        default=None, description="The worker identity of the initial sender of this message"
    )


class InfrahubEvent(BaseModel):
    meta: EventMeta | None = None

    id: UUID = Field(
        default_factory=uuid4,
        description="UUID of the event",
    )

    def get_id(self) -> str:
        return str(self.id)

    def get_event_namespace(self) -> str:
        return EVENT_NAMESPACE

    def get_name(self) -> str:
        return f"{self.get_event_namespace()}.unknown"

    def get_resource(self) -> dict[str, str]:
        raise NotImplementedError

    def get_messages(self) -> list[InfrahubMessage]:
        raise NotImplementedError

    def get_related(self) -> list[dict[str, str]]:
        related: list[dict[str, str]] = []

        if not self.meta:
            return related

        if self.meta.account_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.account.{self.meta.account_id}",
                    "prefect.resource.role": "account",
                }
            )

        if self.meta.request_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.request.{self.meta.request_id}",
                    "prefect.resource.role": "request",
                }
            )

        if self.meta.initiator_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.source.{self.meta.initiator_id}",
                    "prefect.resource.role": "event_source",
                }
            )

        return related

    def get_payload(self) -> dict[str, Any]:
        return {}

    def get_message_meta(self) -> Meta:
        meta = Meta()
        if not self.meta:
            return meta

        if self.meta.initiator_id:
            meta.initiator_id = self.meta.initiator_id
        if self.meta.request_id:
            meta.initiator_id = self.meta.request_id

        return meta


class InfrahubBranchEvent(InfrahubEvent):
    branch: str = Field(..., description="The branch on which the event happend")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": "infrahub.branch",
                "prefect.resource.name": self.branch,
                "prefect.resource.role": "branch",
            }
        )
        return related


class UpdateStatus(str, Enum):
    UNMODIFIED = "unmodified"
    ADDED = "added"
    UPDATED = "updated"
    REMOVED = "removed"


###############################################################################
# Properties
###############################################################################


class Property(BaseModel):
    name: str = Field(..., description="The name of the property")
    value: str | bool = Field(
        ...,
        description="The value of the property, the type of value will be determined based on what kind of property it is",
    )

    @computed_field
    def value_type(self) -> str:
        """The value_type of the property, used to help external systems

        Would be Boolean for the is_visible, is_protected type properties or Text for owner and source
        """
        if isinstance(self.value, str):
            return "Text"

        return "Boolean"


class UpdatedProperty(BaseModel):
    name: str = Field(..., description="The name of the property")
    value_current: str | bool = Field(..., description="The updated value of the property")
    value_previous: str | bool | None = Field(
        ...,
        description="The previous value of the property, a `null` value indicates that the property didn't previously have a value",
    )

    @computed_field
    def value_type(self) -> str:
        """The value_type of the property, used to help external systems"""
        if isinstance(self.value_current, str):
            return "Text"

        return "Boolean"

    @computed_field
    def value_update_status(self) -> UpdateStatus:
        """Indicate how the value was changed during this update"""
        if self.value_current == self.value_previous:
            return UpdateStatus.UNMODIFIED
        if self.value_previous is not None and self.value_current is None:
            return UpdateStatus.REMOVED
        if self.value_previous is None and self.value_current is not None:
            return UpdateStatus.ADDED

        return UpdateStatus.UPDATED


###############################################################################
# Attributes
###############################################################################


class CreatedAttribute(BaseModel):
    name: str = Field(..., description="The name of the attribute")
    value: Any = Field(..., description="The value used during creation of this attribute")
    properties: list[Property] = Field(
        default_factory=list, description="Properties defined for the attribute during creation"
    )

    @computed_field
    def value_type(self) -> str:
        """The value_type of the attribute, used to help external systems"""

        # Add more types
        if isinstance(self.value, str):
            return "Text"

        return "Boolean"


class UpdatedAttribute(BaseModel):
    name: str = Field(..., description="The name of the attribute")
    value_current: Any = Field(..., description="The current value of the attribute")
    value_previous: Any = Field(..., description="The previous value of the attribute")
    updated_properties: list[UpdatedProperty] = Field(
        default_factory=list, description="The properties that were updated during this update"
    )

    @computed_field
    def value_update_status(self) -> UpdateStatus:
        """Indicate how the peer was changed during this update"""
        if self.value_current == self.value_previous:
            return UpdateStatus.UNMODIFIED
        if self.value_previous is not None and self.value_current is None:
            return UpdateStatus.REMOVED
        if self.value_previous is None and self.value_current is not None:
            return UpdateStatus.ADDED

        return UpdateStatus.UPDATED

    @computed_field
    def value_type(self) -> str:
        """The value_type of the attribute, used to help external systems

        The value_type will be based on the current or previous value of this attribute
        """

        # Add more types
        if isinstance(self.value_current, str):
            return "Text"

        return "Boolean"


###############################################################################
# Relationships
###############################################################################


class Relationship(BaseModel):
    peer_id: str = Field(..., description="The ID of the peer on the remote end of this relationship")
    peer_kind: str = Field(..., description="The node kind of the remote peer")
    properties: list[Property] = Field(default_factory=list, description="The properties of this relationship")


class CreatedRelationshipCardinalityOne(Relationship):
    name: str = Field(..., description="The name of the relationship")

    @computed_field
    def cardinality(self) -> str:
        return "one"


class CreatedRelationshipCardinalityMany(BaseModel):
    name: str = Field(..., description="The name of the relationship")
    peers: list[Relationship] = Field(
        default_factory=list, description="The peers defined during the creation of this relationship"
    )

    @computed_field
    def cardinality(self) -> str:
        return "many"


class UpdatedRelationshipCardinalityOne(BaseModel):
    name: str = Field(..., description="The name of the relationship")
    peer_id_previous: str | None = Field(..., description="The previous peer of this relationship")
    peer_kind_previous: str | None = Field(..., description="The node kind of the previous peer")
    peer_id_current: str | None = Field(..., description="The current peer of this relationship")
    peer_kind_current: str | None = Field(..., description="The node kind of the current peer")
    properties: list[UpdatedProperty] = Field(
        default_factory=list, description="Changes to properties of this relationship if any were made"
    )

    @computed_field
    def cardinality(self) -> str:
        return "one"

    @computed_field
    def peer_status(self) -> UpdateStatus:
        """Indicate how the peer was changed during this update"""
        if self.peer_id_previous == self.peer_id_current:
            return UpdateStatus.UNMODIFIED
        if self.peer_id_previous and not self.peer_id_current:
            return UpdateStatus.REMOVED
        if self.peer_id_current and not self.peer_id_previous:
            return UpdateStatus.ADDED

        return UpdateStatus.UPDATED


class UpdatedRelationshipPeer(BaseModel):
    peer_id: str = Field(..., description="The ID of the peer")
    peer_kind: str = Field(..., description="The node kind of the peer")
    peer_status: UpdateStatus = Field(
        ..., description="Indicate how the relationship to this peer was changed in this update"
    )
    properties: list[UpdatedProperty] = Field(
        default_factory=list, description="Changes to properties of this relationship if any were made"
    )


class UpdatedRelationshipCardinalityMany(BaseModel):
    name: str
    peers: list[UpdatedRelationshipPeer] = Field(default_factory=list)

    @computed_field
    def cardinality(self) -> str:
        return "many"


###############################################################################
# Nodes
###############################################################################


class MutatedNode(BaseModel):
    node_id: str
    node_kind: str
    display_label: str


class CreatedNode(MutatedNode):
    """Emitted when a node is created"""

    attributes: list[CreatedAttribute] = Field(default_factory=list)
    relationships: list[CreatedRelationshipCardinalityOne | CreatedRelationshipCardinalityMany] = Field(
        default_factory=list
    )


class DeletedNode(MutatedNode):
    """Emitted when a node is deleted

    It is assumed that all attributes and relationships are deleted during this event
    """


class UpdatedNode(MutatedNode):
    """Emitted when a node is updated"""

    attributes: list[UpdatedAttribute] = Field(default_factory=list)
    relationships: list[UpdatedRelationshipCardinalityOne | UpdatedRelationshipCardinalityMany] = Field(
        default_factory=list
    )
