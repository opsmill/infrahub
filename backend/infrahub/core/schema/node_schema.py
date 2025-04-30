from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import AllowOverrideType, InfrahubKind

from .generated.node_schema import GeneratedNodeSchema
from .generic_schema import GenericSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class NodeSchema(GeneratedNodeSchema):
    @property
    def is_node_schema(self) -> bool:
        return True

    @property
    def is_generic_schema(self) -> bool:
        return False

    @property
    def is_profile_schema(self) -> bool:
        return False

    @property
    def is_template_schema(self) -> bool:
        return False

    def validate_inheritance(self, interface: GenericSchema) -> None:
        """Perform checks specific to inheritance from Generics.

        Checks:
            - Check that protected attributes and relationships are not overridden before inheriting them from interface.
            - Check that the attribute types to be inherited are same kind.
        """
        for attribute in self.attributes:
            if attribute.name in interface.attribute_names:
                if (
                    not attribute.inherited
                    and interface.get_attribute(attribute.name).allow_override == AllowOverrideType.NONE
                ):
                    raise ValueError(
                        f"{self.kind}'s attribute {attribute.name} inherited from {interface.kind} cannot be overriden"
                    )

                interface_attr = interface.get_attribute(attribute.name)
                # Check existing inherited attribute kind is the same as the incoming inherited attribute
                if attribute.kind != interface_attr.kind:
                    raise ValueError(
                        f"{self.kind}.{attribute.name} inherited from {interface.namespace}{interface.name} must be the same kind "
                        f'["{interface_attr.kind}", "{attribute.kind}"]'
                    )
                if attribute.optional != interface_attr.optional:
                    raise ValueError(
                        f"{self.kind}.{attribute.name} inherited from {interface.namespace}{interface.name} must have the same value for property "
                        f'"optional" ["{interface_attr.optional}", "{attribute.optional}"]'
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
        existing_inherited_attributes: dict[str, int] = {
            item.name: idx for idx, item in enumerate(self.attributes) if item.inherited
        }
        existing_inherited_relationships: dict[str, int] = {
            item.name: idx for idx, item in enumerate(self.relationships) if item.inherited
        }
        existing_inherited_fields = list(existing_inherited_attributes.keys()) + list(
            existing_inherited_relationships.keys()
        )

        properties_to_inherit = [
            "human_friendly_id",
            "display_labels",
            "default_filter",
            "menu_placement",
            "uniqueness_constraints",
            "icon",
            "order_by",
        ]
        for prop_name in properties_to_inherit:
            if getattr(interface, prop_name) and not getattr(self, prop_name):
                setattr(self, prop_name, getattr(interface, prop_name))

        for attribute in interface.attributes:
            if attribute.name in self.valid_local_names:
                continue

            new_attribute = attribute.duplicate()
            new_attribute.id = None
            new_attribute.inherited = True

            if attribute.name not in existing_inherited_fields:
                self.attributes.append(new_attribute)
            else:
                item_idx = existing_inherited_attributes[attribute.name]
                self.attributes[item_idx].update_from_generic(other=new_attribute)

        for relationship in interface.relationships:
            if relationship.name in self.valid_local_names:
                continue

            new_relationship = relationship.duplicate()
            new_relationship.id = None
            new_relationship.inherited = True

            if relationship.name not in existing_inherited_fields:
                self.relationships.append(new_relationship)
            else:
                item_idx = existing_inherited_relationships[relationship.name]
                self.relationships[item_idx].update_from_generic(other=new_relationship)

    def get_hierarchy_schema(self, db: InfrahubDatabase, branch: Branch | str | None = None) -> GenericSchema:
        if not self.hierarchy:
            raise ValueError("The node is not part of a hierarchy")
        schema = db.schema.get(name=self.hierarchy, branch=branch)
        if not isinstance(schema, GenericSchema):
            raise TypeError
        return schema

    def get_labels(self) -> list[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""

        labels: list[str] = [self.kind] + self.inherit_from
        if self.namespace not in ["Schema", "Internal"] and InfrahubKind.GENERICGROUP not in self.inherit_from:
            labels.append(InfrahubKind.NODE)
        return labels

    def is_ip_prefix(self) -> bool:
        """Return whether a node is a derivative of built-in IP prefixes."""
        return InfrahubKind.IPPREFIX in self.inherit_from

    def is_ip_address(self) -> bool:
        """Return whether a node is a derivative of built-in IP addreses."""
        return InfrahubKind.IPADDRESS in self.inherit_from
