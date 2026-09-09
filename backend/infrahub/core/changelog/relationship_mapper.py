from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from infrahub.core.constants import RelationshipCardinality

from .models import RelationshipCardinalityManyChangelog, RelationshipCardinalityOneChangelog

if TYPE_CHECKING:
    from infrahub.core.manager import RelationshipSchema
    from infrahub.core.query.relationship import RelationshipPeerData
    from infrahub.core.relationship.model import Relationship


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
            self.cardinality_one_relationship.set_parent_from_relationship(rel_kind=self.schema.kind)
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
