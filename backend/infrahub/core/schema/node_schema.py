from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Union

from infrahub.core import registry
from infrahub.core.constants import AllowOverrideType, InfrahubKind

from .generated.node_schema import GeneratedNodeSchema
from .generic_schema import GenericSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


class NodeSchema(GeneratedNodeSchema):
    def validate_inheritance(self, interface: GenericSchema) -> None:
        """Check that protected attributes and relationships are not overriden before inheriting them from interface."""
        for attribute in self.attributes:
            if (
                attribute.name in interface.attribute_names
                and not attribute.inherited
                and interface.get_attribute(attribute.name).allow_override == AllowOverrideType.NONE
            ):
                raise ValueError(
                    f"{self.kind}'s attribute {attribute.name} inherited from {interface.kind} cannot be overriden"
                )

        for relationship in self.relationships:
            if (
                relationship.name in interface.relationship_names
                and not relationship.inherited
                and interface.get_relationship(relationship.name).allow_override == AllowOverrideType.NONE
            ):
                raise ValueError(
                    f"{self.kind}'s relationship {relationship.name} inherited from {interface.kind} cannot be overriden"
                )

    def inherit_from_interface(self, interface: GenericSchema) -> None:
        existing_inherited_attributes = {item.name: idx for idx, item in enumerate(self.attributes) if item.inherited}
        existing_inherited_relationships = {
            item.name: idx for idx, item in enumerate(self.relationships) if item.inherited
        }
        existing_inherited_fields = list(existing_inherited_attributes.keys()) + list(
            existing_inherited_relationships.keys()
        )

        for attribute in interface.attributes:
            if attribute.name in self.valid_input_names:
                continue

            new_attribute = attribute.duplicate()
            new_attribute.inherited = True

            if attribute.name not in existing_inherited_fields:
                self.attributes.append(new_attribute)
            else:
                item_idx = existing_inherited_attributes[attribute.name]
                self.attributes[item_idx] = new_attribute

        for relationship in interface.relationships:
            if relationship.name in self.valid_input_names:
                continue

            new_relationship = relationship.duplicate()
            new_relationship.inherited = True

            if relationship.name not in existing_inherited_fields:
                self.relationships.append(new_relationship)
            else:
                item_idx = existing_inherited_relationships[relationship.name]
                self.relationships[item_idx] = new_relationship

    def get_hierarchy_schema(self, branch: Optional[Union[Branch, str]] = None) -> GenericSchema:
        if not self.hierarchy:
            raise ValueError("The node is not part of a hierarchy")
        schema = registry.schema.get(name=self.hierarchy, branch=branch)
        if not isinstance(schema, GenericSchema):
            raise TypeError
        return schema

    def get_labels(self) -> List[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""

        labels: List[str] = [self.kind] + self.inherit_from
        if self.namespace not in ["Schema", "Internal"] and InfrahubKind.GENERICGROUP not in self.inherit_from:
            labels.append("CoreNode")
        return labels

    def is_ip_prefix(self) -> bool:
        """Return whether a node is a derivative of built-in IP prefixes."""
        return InfrahubKind.IPPREFIX in self.inherit_from

    def is_ip_address(self) -> bool:
        """Return whether a node is a derivative of built-in IP addreses."""
        return InfrahubKind.IPADDRESS in self.inherit_from
