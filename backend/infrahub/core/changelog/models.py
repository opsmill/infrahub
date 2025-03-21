from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, cast
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr, computed_field, field_validator, model_validator

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipCardinality, RelationshipKind

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.manager import RelationshipSchema
    from infrahub.core.query.relationship import RelationshipPeerData
    from infrahub.core.relationship.model import Relationship
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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
    value: Any = Field(default=None, description="The current value of the attribute")
    value_previous: Any = Field(default=None, description="The previous value of the attribute")
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

    def set_value(self, value: Any) -> None:
        if isinstance(value, str) and value == NULL_VALUE:
            self.value = None
            return
        self.value = value

    def set_value_previous(self, value: Any) -> None:
        if isinstance(value, str) and value == NULL_VALUE:
            self.value_previous = None
            return
        self.value_previous = value

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
    _parent: ChangelogRelatedNode | None = PrivateAttr(default=None)

    @property
    def parent(self) -> ChangelogRelatedNode | None:
        return self._parent

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

    def set_parent(self, parent_id: str, parent_kind: str) -> None:
        self._parent = ChangelogRelatedNode(node_id=parent_id, node_kind=parent_kind)

    def set_parent_from_relationship(self, rel_kind: RelationshipKind) -> None:
        if rel_kind == RelationshipKind.PARENT:
            if (
                self.peer_status in [DiffAction.ADDED, DiffAction.UNCHANGED, DiffAction.UPDATED]
                and self.peer_id
                and self.peer_kind
            ):
                self._parent = ChangelogRelatedNode(node_id=self.peer_id, node_kind=self.peer_kind)
            elif self.peer_id_previous and self.peer_kind_previous:
                self._parent = ChangelogRelatedNode(node_id=self.peer_id_previous, node_kind=self.peer_kind_previous)

    @property
    def is_empty(self) -> bool:
        return self.peer_status == DiffAction.UNCHANGED and not self.properties


class RelationshipPeerChangelog(BaseModel):
    peer_id: str = Field(..., description="The ID of the peer")
    peer_kind: str = Field(..., description="The node kind of the peer")
    peer_status: DiffAction = Field(
        ..., description="Indicate how the relationship to this peer was changed in this update"
    )
    properties: dict[str, PropertyChangelog] = Field(
        default_factory=dict, description="Changes to properties of this relationship if any were made"
    )

    def add_property(self, name: str, value_current: bool | str | None, value_previous: bool | str | None) -> None:
        self.properties[name] = PropertyChangelog(name=name, value=value_current, value_previous=value_previous)


class RelationshipCardinalityManyChangelog(BaseModel):
    name: str
    peers: list[RelationshipPeerChangelog] = Field(default_factory=list)

    @computed_field
    def cardinality(self) -> str:
        return "many"

    def add_new_peer(self, relationship: Relationship) -> None:
        properties: dict[str, PropertyChangelog] = {}
        properties["is_protected"] = PropertyChangelog(
            name="is_protected", value=relationship.is_protected, value_previous=None
        )
        properties["is_visible"] = PropertyChangelog(
            name="is_visible", value=relationship.is_protected, value_previous=None
        )
        if owner := getattr(relationship, "owner_id", None):
            properties["owner"] = PropertyChangelog(name="owner", value=owner, value_previous=None)
        if source := getattr(relationship, "source_id", None):
            properties["source"] = PropertyChangelog(name="source_id", value=source, value_previous=None)

        self.peers.append(
            RelationshipPeerChangelog(
                peer_id=relationship.get_peer_id(),
                peer_kind=relationship.get_peer_kind(),
                peer_status=DiffAction.ADDED,
                properties=properties,
            )
        )

    def remove_peer(self, peer_id: str, peer_kind: str) -> None:
        self.peers.append(
            RelationshipPeerChangelog(
                peer_id=peer_id,
                peer_kind=peer_kind,
                peer_status=DiffAction.REMOVED,
            )
        )

    @property
    def is_empty(self) -> bool:
        return not self.peers


class ChangelogRelatedNode(BaseModel):
    node_id: str
    node_kind: str


class NodeChangelog(BaseModel):
    """Emitted when a node is updated"""

    node_id: str
    node_kind: str
    display_label: str

    attributes: dict[str, AttributeChangelog] = Field(default_factory=dict)
    relationships: dict[str, RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog] = Field(
        default_factory=dict
    )

    _parent: ChangelogRelatedNode | None = PrivateAttr(default=None)

    @property
    def parent(self) -> ChangelogRelatedNode | None:
        return self._parent

    @property
    def updated_fields(self) -> list[str]:
        """Return a list of update fields i.e. attributes and relationships"""
        return list(self.relationships.keys()) + list(self.attributes.keys())

    @property
    def has_changes(self) -> bool:
        return len(self.updated_fields) > 0

    @property
    def root_node_id(self) -> str:
        """Return the top level node_id"""
        if self.parent:
            return self.parent.node_id
        return self.node_id

    def add_parent(self, parent: ChangelogRelatedNode) -> None:
        self._parent = parent

    def add_parent_from_relationship(self, parent: Relationship) -> None:
        self._parent = ChangelogRelatedNode(node_id=parent.get_peer_id(), node_kind=parent.get_peer_kind())

    def create_relationship(self, relationship: Relationship) -> None:
        if relationship.schema.cardinality == RelationshipCardinality.ONE:
            peer_id = relationship.get_peer_id()
            peer_kind = relationship.get_peer_kind()
            if relationship.schema.kind == RelationshipKind.PARENT:
                self._parent = ChangelogRelatedNode(node_id=peer_id, node_kind=peer_kind)
            changelog_relationship = RelationshipCardinalityOneChangelog(
                name=relationship.schema.name,
                peer_id=peer_id,
                peer_kind=peer_kind,
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
        elif relationship.schema.cardinality == RelationshipCardinality.MANY:
            if relationship.schema.name not in self.relationships:
                self.relationships[relationship.schema.name] = RelationshipCardinalityManyChangelog(
                    name=relationship.schema.name
                )
            relationship_container = cast(
                RelationshipCardinalityManyChangelog, self.relationships[relationship.schema.name]
            )

            relationship_container.add_new_peer(relationship=relationship)

    def delete_relationship(self, relationship: Relationship) -> None:
        if relationship.schema.cardinality == RelationshipCardinality.ONE:
            peer_id = relationship.get_peer_id()
            peer_kind = relationship.get_peer_kind()
            changelog_relationship = RelationshipCardinalityOneChangelog(
                name=relationship.schema.name,
                peer_id_previous=peer_id,
                peer_kind_previous=peer_kind,
            )
            self.relationships[changelog_relationship.name] = changelog_relationship
        elif relationship.schema.cardinality == RelationshipCardinality.MANY:
            if relationship.schema.name not in self.relationships:
                self.relationships[relationship.schema.name] = RelationshipCardinalityManyChangelog(
                    name=relationship.schema.name
                )
            relationship_container = cast(
                RelationshipCardinalityManyChangelog, self.relationships[relationship.schema.name]
            )
            relationship_container.remove_peer(
                peer_id=relationship.get_peer_id(), peer_kind=relationship.get_peer_kind()
            )

    def add_attribute(self, attribute: AttributeChangelog) -> None:
        if attribute.has_updates:
            self.attributes[attribute.name] = attribute

    def add_relationship(
        self, relationship_changelog: RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog
    ) -> None:
        if isinstance(relationship_changelog, RelationshipCardinalityOneChangelog) and relationship_changelog.parent:
            self.add_parent(parent=relationship_changelog.parent)
        if relationship_changelog.is_empty:
            return

        self.relationships[relationship_changelog.name] = relationship_changelog

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

    def get_related_nodes(self) -> list[ChangelogRelatedNode]:
        related_nodes: dict[str, ChangelogRelatedNode] = {}
        for relationship in self.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog):
                if relationship.peer_id and relationship.peer_kind:
                    related_nodes[relationship.peer_id] = ChangelogRelatedNode(
                        node_id=relationship.peer_id, node_kind=relationship.peer_kind
                    )
                if relationship.peer_id_previous and relationship.peer_kind_previous:
                    related_nodes[relationship.peer_id_previous] = ChangelogRelatedNode(
                        node_id=relationship.peer_id_previous, node_kind=relationship.peer_kind_previous
                    )
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                for peer in relationship.peers:
                    related_nodes[peer.peer_id] = ChangelogRelatedNode(node_id=peer.peer_id, node_kind=peer.peer_kind)

        if self.parent:
            related_nodes[self.parent.node_id] = self.parent

        return list(related_nodes.values())


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
        elif self.schema.cardinality == RelationshipCardinality.MANY:
            self.cardinality_many_relationship.remove_peer(
                peer_id=str(peer_data.peer_id), peer_kind=peer_data.peer_kind
            )

    def _set_cardinality_one_peer(self, relationship: Relationship) -> None:
        self.cardinality_one_relationship.peer_id = relationship.peer_id
        self.cardinality_one_relationship.peer_kind = relationship.get_peer_kind()
        self.cardinality_one_relationship.set_parent_from_relationship(rel_kind=relationship.schema.kind)

    def add_parent_from_relationship(self, relationship: Relationship) -> None:
        if self.schema.cardinality == RelationshipCardinality.ONE:
            self.cardinality_one_relationship.set_parent(
                parent_id=relationship.get_peer_id(), parent_kind=relationship.get_peer_kind()
            )

    def add_peer_from_relationship(self, relationship: Relationship) -> None:
        if self.schema.cardinality == RelationshipCardinality.ONE:
            self._set_cardinality_one_peer(relationship=relationship)
        elif self.schema.cardinality == RelationshipCardinality.MANY:
            self.cardinality_many_relationship.add_new_peer(relationship=relationship)

    def add_updated_relationship(
        self, relationship: Relationship, old_data: RelationshipPeerData, properties_to_update: list[str]
    ) -> None:
        if self.schema.cardinality == RelationshipCardinality.ONE:
            self._set_cardinality_one_peer(relationship=relationship)
            self.cardinality_one_relationship.peer_id_previous = self.cardinality_one_relationship.peer_id
            self.cardinality_one_relationship.peer_kind_previous = self.cardinality_one_relationship.peer_kind
            for property_to_update in properties_to_update:
                previous_property = old_data.properties.get(property_to_update)
                previous_value: str | bool | None = None
                if previous_property:
                    if isinstance(previous_property.value, UUID):
                        previous_value = str(previous_property.value)
                    else:
                        previous_value = previous_property.value
                property_name = (
                    property_to_update if property_to_update not in ["source", "owner"] else f"{property_to_update}_id"
                )
                self.cardinality_one_relationship.add_property(
                    name=property_to_update,
                    value_current=getattr(relationship, property_name),
                    value_previous=previous_value,
                )
            self.cardinality_one_relationship.set_parent_from_relationship(rel_kind=relationship.schema.kind)

    def delete_relationship(self, peer_id: str, peer_kind: str, rel_schema: RelationshipSchema) -> None:
        if self.schema.cardinality == RelationshipCardinality.ONE:
            self.cardinality_one_relationship.peer_id_previous = peer_id
            self.cardinality_one_relationship.peer_kind_previous = peer_kind
            self.cardinality_one_relationship.set_parent_from_relationship(rel_kind=rel_schema.kind)

        elif self.schema.cardinality == RelationshipCardinality.MANY:
            self.cardinality_many_relationship.remove_peer(peer_id=peer_id, peer_kind=peer_kind)

    @property
    def changelog(self) -> RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog:
        match self.schema.cardinality:
            case RelationshipCardinality.ONE:
                return self.cardinality_one_relationship
            case RelationshipCardinality.MANY:
                return self.cardinality_many_relationship


class RelationshipChangelogGetter:
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self._db = db
        self._branch = branch

    async def get_changelogs(self, primary_changelog: NodeChangelog) -> list[NodeChangelog]:
        """Return secondary changelogs based on this update

        These will typically include updates to relationships on other nodes.
        """
        schema_branch = self._db.schema.get_schema_branch(name=self._branch.name)
        node_schema = schema_branch.get(name=primary_changelog.node_kind, duplicate=False)
        secondaries: list[NodeChangelog] = []

        for relationship in primary_changelog.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog):
                secondaries.extend(
                    self._parse_cardinality_one_relationship(
                        relationship=relationship,
                        node_schema=node_schema,
                        primary_changelog=primary_changelog,
                        schema_branch=schema_branch,
                    )
                )
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                secondaries.extend(
                    self._parse_cardinality_many_relationship(
                        relationship=relationship,
                        node_schema=node_schema,
                        primary_changelog=primary_changelog,
                        schema_branch=schema_branch,
                    )
                )

        return secondaries

    def _parse_cardinality_one_relationship(
        self,
        relationship: RelationshipCardinalityOneChangelog,
        node_schema: MainSchemaTypes,
        primary_changelog: NodeChangelog,
        schema_branch: SchemaBranch,
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        rel_schema = node_schema.get_relationship(name=relationship.name)

        if relationship.peer_status == DiffAction.ADDED:
            peer_schema = schema_branch.get(name=str(relationship.peer_kind), duplicate=False)
            secondaries.extend(
                self._process_added_peers(
                    peer_id=str(relationship.peer_id),
                    peer_kind=str(relationship.peer_kind),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                )
            )

        elif relationship.peer_status == DiffAction.UPDATED:
            peer_schema = schema_branch.get(name=str(relationship.peer_kind), duplicate=False)
            secondaries.extend(
                self._process_added_peers(
                    peer_id=str(relationship.peer_id),
                    peer_kind=str(relationship.peer_kind),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                )
            )
            secondaries.extend(
                self._process_removed_peers(
                    peer_schema=peer_schema,
                    peer_id=str(relationship.peer_id_previous),
                    peer_kind=str(relationship.peer_kind_previous),
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                )
            )

        elif relationship.peer_status == DiffAction.REMOVED:
            peer_schema = schema_branch.get(name=str(relationship.peer_kind_previous), duplicate=False)

            secondaries.extend(
                self._process_removed_peers(
                    peer_id=str(relationship.peer_id_previous),
                    peer_kind=str(relationship.peer_kind_previous),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                )
            )

        return secondaries

    def _parse_cardinality_many_relationship(
        self,
        relationship: RelationshipCardinalityManyChangelog,
        node_schema: MainSchemaTypes,
        primary_changelog: NodeChangelog,
        schema_branch: SchemaBranch,
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        rel_schema = node_schema.get_relationship(name=relationship.name)

        for peer in relationship.peers:
            if peer.peer_status == DiffAction.ADDED:
                peer_schema = schema_branch.get(name=peer.peer_kind)
                secondaries.extend(
                    self._process_added_peers(
                        peer_id=peer.peer_id,
                        peer_kind=peer.peer_kind,
                        peer_schema=peer_schema,
                        rel_schema=rel_schema,
                        primary_changelog=primary_changelog,
                    )
                )

            elif peer.peer_status == DiffAction.REMOVED:
                peer_schema = schema_branch.get(name=peer.peer_kind)
                secondaries.extend(
                    self._process_removed_peers(
                        peer_id=peer.peer_id,
                        peer_kind=peer.peer_kind,
                        peer_schema=peer_schema,
                        rel_schema=rel_schema,
                        primary_changelog=primary_changelog,
                    )
                )

        return secondaries

    def _process_added_peers(
        self,
        peer_id: str,
        peer_kind: str,
        peer_schema: MainSchemaTypes,
        rel_schema: RelationshipSchema,
        primary_changelog: NodeChangelog,
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        peer_relation = peer_schema.get_relationship_by_identifier(id=str(rel_schema.identifier), raise_on_error=False)
        if peer_relation:
            node_changelog = NodeChangelog(
                node_id=peer_id,
                node_kind=peer_kind,
                display_label="n/a",
            )
            if peer_relation.cardinality == RelationshipCardinality.ONE:
                node_changelog.relationships[peer_relation.name] = RelationshipCardinalityOneChangelog(
                    name=peer_relation.name,
                    peer_id=primary_changelog.node_id,
                    peer_kind=primary_changelog.node_kind,
                )
                secondaries.append(node_changelog)
            elif peer_relation.cardinality == RelationshipCardinality.MANY:
                node_changelog.relationships[peer_relation.name] = RelationshipCardinalityManyChangelog(
                    name=peer_relation.name,
                    peers=[
                        RelationshipPeerChangelog(
                            peer_id=primary_changelog.node_id,
                            peer_kind=primary_changelog.node_kind,
                            peer_status=DiffAction.ADDED,
                        )
                    ],
                )
                secondaries.append(node_changelog)

        return secondaries

    def _process_removed_peers(
        self,
        peer_id: str,
        peer_kind: str,
        peer_schema: MainSchemaTypes,
        rel_schema: RelationshipSchema,
        primary_changelog: NodeChangelog,
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        peer_relation = peer_schema.get_relationship_by_identifier(id=str(rel_schema.identifier), raise_on_error=False)
        if peer_relation:
            node_changelog = NodeChangelog(
                node_id=peer_id,
                node_kind=peer_kind,
                display_label="n/a",
            )
            if peer_relation.cardinality == RelationshipCardinality.ONE:
                node_changelog.relationships[peer_relation.name] = RelationshipCardinalityOneChangelog(
                    name=peer_relation.name,
                    peer_id_previous=primary_changelog.node_id,
                    peer_kind_previous=primary_changelog.node_kind,
                )
                secondaries.append(node_changelog)
            elif peer_relation.cardinality == RelationshipCardinality.MANY:
                node_changelog.relationships[peer_relation.name] = RelationshipCardinalityManyChangelog(
                    name=peer_relation.name,
                    peers=[
                        RelationshipPeerChangelog(
                            peer_id=primary_changelog.node_id,
                            peer_kind=primary_changelog.node_kind,
                            peer_status=DiffAction.REMOVED,
                        )
                    ],
                )
                secondaries.append(node_changelog)

        return secondaries
