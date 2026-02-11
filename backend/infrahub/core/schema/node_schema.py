from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import OBJECT_TEMPLATE_RELATIONSHIP_NAME, AllowOverrideType, InfrahubKind, RelationshipKind

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

    @property
    def is_ip_prefix(self) -> bool:
        """Return whether a node is a derivative of built-in IP prefixes."""
        return InfrahubKind.IPPREFIX in self.inherit_from

    @property
    def is_ip_address(self) -> bool:
        """Return whether a node is a derivative of built-in IP addreses."""
        return InfrahubKind.IPADDRESS in self.inherit_from

    @property
    def is_file_object(self) -> bool:
        """Return whether a node is a derivative of built-in file objects."""
        return InfrahubKind.FILEOBJECT in self.inherit_from

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

        for relationship in self.relationships:
            if relationship.name in interface.relationship_names and not relationship.inherited:
                interface_relationship = interface.get_relationship(relationship.name)
                if interface_relationship.allow_override == AllowOverrideType.NONE:
                    raise ValueError(
                        f"{self.kind}'s relationship {relationship.name} inherited from {interface.kind} cannot be overriden"
                    )
                if (
                    relationship.kind == RelationshipKind.HIERARCHY
                    or relationship.name == OBJECT_TEMPLATE_RELATIONSHIP_NAME
                ):
                    continue
                if relationship.peer != interface_relationship.peer:
                    raise ValueError(
                        f"{self.kind}'s relationship {relationship.name} inherited from {interface.kind} must have the same peer "
                        f"({interface_relationship.peer} != {relationship.peer})"
                    )

    def get_hierarchy_schema(
        self, db: InfrahubDatabase, branch: Branch | str | None = None, duplicate: bool = False
    ) -> GenericSchema:
        if not self.hierarchy:
            raise ValueError("The node is not part of a hierarchy")
        schema = db.schema.get(name=self.hierarchy, branch=branch, duplicate=duplicate)
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
