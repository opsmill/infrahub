from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipCardinality

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.manager import RelationshipSchema
    from infrahub.core.query.relationship import RelationshipPeerData
    from infrahub.core.relationship.model import Relationship


class PropertyChangelog(BaseModel):
    name: str = Field(..., description="The name of the property")
    value: str | bool | None = Field(..., description="The updated or current value of the property")
    value_previous: str | bool | None = Field(
        ...,
        description="The previous value of the property, a `null` value indicates that the property didn't previously have a value",
    )

    @computed_field
    def value_type(self) -> str:
        """The value_type of the property, used to help external systems"""
        if isinstance(self.value, str):
            return "Text"

        return "Boolean"

    @computed_field
    def value_update_status(self) -> DiffAction:
        """Indicate how the value was changed during this update"""
        if self.value == self.value_previous:
            return DiffAction.UNCHANGED
        if self.value_previous is not None and self.value is None:
            return DiffAction.REMOVED
        if self.value_previous is None and self.value is not None:
            return DiffAction.ADDED

        return DiffAction.UPDATED


class AttributeChangelog(BaseModel):
    name: str = Field(..., description="The name of the attribute")
    value: Any = Field(..., description="The current value of the attribute")
    value_previous: Any = Field(..., description="The previous value of the attribute")
    properties: dict[str, PropertyChangelog] = Field(
        default_factory=dict, description="The properties that were updated during this update"
    )
    kind: str = Field(..., description="The attribute kind")

    @computed_field
    def value_update_status(self) -> DiffAction:
        """Indicate how the peer was changed during this update"""
        if self.value == self.value_previous:
            return DiffAction.UNCHANGED
        if self.value_previous is not None and self.value is None:
            return DiffAction.REMOVED
        if self.value_previous is None and self.value is not None:
            return DiffAction.ADDED

        return DiffAction.UPDATED

    def add_property(self, name: str, value_current: bool | str | None, value_previous: bool | str | None) -> None:
        self.properties[name] = PropertyChangelog(name=name, value=value_current, value_previous=value_previous)

    @property
    def has_updates(self) -> bool:
        if self.value_update_status != DiffAction.UNCHANGED or self.properties:
            return True
        return False

    @field_validator("value", "value_previous")
    @classmethod
    def convert_null_values(cls, value: Any) -> Any:
        if isinstance(value, str) and value == NULL_VALUE:
            return None
        return value

    @model_validator(mode="after")
    def filter_sensitive(self) -> Self:
        if self.kind in ["HashedPassword", "Password"]:
            if self.value is not None:
                self.value = "***"
            if self.value_previous is not None:
                self.value_previous = "***"

        return self


class RelationshipCardinalityOneChangelog(BaseModel):
    name: str = Field(..., description="The name of the relationship")
    peer_id_previous: str | None = Field(default=None, description="The previous peer of this relationship")
    peer_kind_previous: str | None = Field(default=None, description="The node kind of the previous peer")
    peer_id: str | None = Field(default=None, description="The current peer of this relationship")
    peer_kind: str | None = Field(default=None, description="The node kind of the current peer")
    properties: dict[str, PropertyChangelog] = Field(
        default_factory=dict, description="Changes to properties of this relationship if any were made"
    )

    @computed_field
    def cardinality(self) -> str:
        return "one"

    @computed_field
    def peer_status(self) -> DiffAction:
        """Indicate how the peer was changed during this update"""
        if self.peer_id_previous == self.peer_id:
            return DiffAction.UNCHANGED
        if self.peer_id_previous and not self.peer_id:
            return DiffAction.REMOVED
        if self.peer_id and not self.peer_id_previous:
            return DiffAction.ADDED
        return DiffAction.UPDATED

    def add_property(self, name: str, value_current: bool | str | None, value_previous: bool | str | None) -> None:
        self.properties[name] = PropertyChangelog(name=name, value=value_current, value_previous=value_previous)


class RelationshipPeerChangelog(BaseModel):
    peer_id: str = Field(..., description="The ID of the peer")
    peer_kind: str = Field(..., description="The node kind of the peer")
    peer_status: DiffAction = Field(
        ..., description="Indicate how the relationship to this peer was changed in this update"
    )
    properties: dict[str, PropertyChangelog] = Field(
        default_factory=dict, description="Changes to properties of this relationship if any were made"
    )


class RelationshipCardinalityManyChangelog(BaseModel):
    name: str
    peers: list[RelationshipPeerChangelog] = Field(default_factory=list)

    @computed_field
    def cardinality(self) -> str:
        return "many"


class NodeChangelog(BaseModel):
    """Emitted when a node is updated"""

    node_id: str
    node_kind: str
    display_label: str

    attributes: dict[str, AttributeChangelog] = Field(default_factory=dict)
    relationships: dict[str, RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog] = Field(
        default_factory=dict
    )

    def create_relationship(self, relationship: Relationship) -> None:
        if relationship.schema.cardinality == RelationshipCardinality.ONE:
            peer_kind_current = relationship.schema.peer
            if not isinstance(relationship._peer, str | None):
                # This check is to check if the peer is a `Node` and avoid a circular import
                peer_kind_current = relationship._peer.get_kind()

            changelog_relationship = RelationshipCardinalityOneChangelog(
                name=relationship.schema.name,
                peer_id=relationship.peer_id,
                peer_kind=peer_kind_current,
            )
            if source_id := getattr(relationship, "source_id", None):
                changelog_relationship.add_property(name="source", value_current=source_id, value_previous=None)
            if owner_id := getattr(relationship, "owner_id", None):
                changelog_relationship.add_property(name="owner", value_current=owner_id, value_previous=None)
            changelog_relationship.add_property(
                name="is_protected", value_current=relationship.is_protected, value_previous=None
            )
            changelog_relationship.add_property(
                name="is_visible", value_current=relationship.is_visible, value_previous=None
            )
            self.relationships[changelog_relationship.name] = changelog_relationship

        # TODO: Fix Cardinality many relationships

    def add_attribute(self, attribute: AttributeChangelog) -> None:
        self.attributes[attribute.name] = attribute

    def add_relationship(
        self, relationship: RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog
    ) -> None:
        self.relationships[relationship.name] = relationship

    def create_attribute(self, attribute: BaseAttribute) -> None:
        changelog_attribute = AttributeChangelog(
            name=attribute.name, value=attribute.value, value_previous=None, kind=attribute.schema.kind
        )
        if source_id := getattr(attribute, "source_id", None):
            changelog_attribute.add_property(name="source", value_current=source_id, value_previous=None)
        if owner_id := getattr(attribute, "owner_id", None):
            changelog_attribute.add_property(name="owner", value_current=owner_id, value_previous=None)
        changelog_attribute.add_property(name="is_protected", value_current=attribute.is_protected, value_previous=None)
        changelog_attribute.add_property(name="is_visible", value_current=attribute.is_visible, value_previous=None)
        self.attributes[changelog_attribute.name] = changelog_attribute


class ChangelogRelationshipMapper:
    def __init__(self, schema: RelationshipSchema) -> None:
        self.schema = schema
        self._cardinality_one_relationship: RelationshipCardinalityOneChangelog | None = None
        self._cardinality_many_relationship: RelationshipCardinalityManyChangelog | None = None

    @property
    def cardinality_one_relationship(self) -> RelationshipCardinalityOneChangelog:
        if not self._cardinality_one_relationship:
            self._cardinality_one_relationship = RelationshipCardinalityOneChangelog(name=self.schema.name)

        return self._cardinality_one_relationship

    @property
    def cardinality_many_relationship(self) -> RelationshipCardinalityManyChangelog:
        if not self._cardinality_many_relationship:
            self._cardinality_many_relationship = RelationshipCardinalityManyChangelog(name=self.schema.name)

        return self._cardinality_many_relationship

    def remove_peer(self, peer_data: RelationshipPeerData) -> None:
        if self.schema.cardinality == RelationshipCardinality.ONE:
            self.cardinality_one_relationship.peer_id_previous = str(peer_data.peer_id)
            self.cardinality_one_relationship.peer_kind_previous = peer_data.peer_kind

    def add_peer_from_relationship(self, relationship: Relationship) -> None:
        peer_kind = relationship.schema.peer
        if self.schema.cardinality == RelationshipCardinality.ONE:
            self.cardinality_one_relationship.peer_id = relationship.peer_id
            if not isinstance(relationship._peer, str | None):
                # This check is to check if the peer is a `Node` and avoid a circular import
                peer_kind = relationship._peer.get_kind()
            self.cardinality_one_relationship.peer_kind = peer_kind

    @property
    def changelog(self) -> RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog:
        match self.schema.cardinality:
            case RelationshipCardinality.ONE:
                return self.cardinality_one_relationship
            case RelationshipCardinality.MANY:
                return self.cardinality_many_relationship
