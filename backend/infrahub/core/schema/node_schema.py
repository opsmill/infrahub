from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import AllowOverrideType, InfrahubKind, RelationshipKind

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
                if relationship.kind != RelationshipKind.HIERARCHY and relationship.peer != interface_relationship.peer:
                    raise ValueError(
                        f"{self.kind}'s relationship {relationship.name} inherited from {interface.kind} must have the same peer "
                        f"({interface_relationship.peer} != {relationship.peer})"
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
            "display_label",
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

        # Build a mapping from source_attribute_id to (index, old_name) for existing inherited attributes
        # This allows us to detect renamed attributes by their source ID
        existing_inherited_attr_by_source_id: dict[str, tuple[int, str]] = {
            item.source_attribute_id: (idx, item.name)
            for idx, item in enumerate(self.attributes)
            if item.inherited and item.source_attribute_id
        }

        # Track renamed attributes to update schema properties (uniqueness_constraints, etc.)
        renamed_attrs: dict[str, str] = {}  # old_name -> new_name

        for attribute in interface.attributes:
            if attribute.name in self.valid_local_names:
                continue

            new_attribute = attribute.duplicate()
            new_attribute.id = None
            new_attribute.inherited = True
            # Store the source generic's attribute ID for rename detection
            new_attribute.source_attribute_id = attribute.id

            # Check if this attribute already exists by source_attribute_id (for rename detection)
            # or by name (for regular updates)
            if attribute.id and attribute.id in existing_inherited_attr_by_source_id:
                # Attribute was renamed in the generic - update the existing one
                item_idx, old_name = existing_inherited_attr_by_source_id[attribute.id]
                if old_name != new_attribute.name:
                    renamed_attrs[old_name] = new_attribute.name
                    # Update tracking structures to prevent stale lookups
                    existing_inherited_attributes.pop(old_name, None)
                    existing_inherited_attributes[new_attribute.name] = item_idx
                    existing_inherited_fields.remove(old_name)
                    existing_inherited_fields.append(new_attribute.name)
                self.attributes[item_idx].update_from_generic(other=new_attribute)
                self.attributes[item_idx].name = new_attribute.name  # Update name explicitly
                self.attributes[item_idx].source_attribute_id = new_attribute.source_attribute_id
            elif attribute.name not in existing_inherited_fields:
                self.attributes.append(new_attribute)
            else:
                item_idx = existing_inherited_attributes[attribute.name]
                self.attributes[item_idx].update_from_generic(other=new_attribute)
                self.attributes[item_idx].source_attribute_id = new_attribute.source_attribute_id

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

        if renamed_attrs:
            if self.uniqueness_constraints:
                self._update_uniqueness_constraints_for_renamed_attributes(renamed_attrs)

            if self.human_friendly_id:
                self._update_hfid_for_renamed_attributes(renamed_attrs)

            if self.order_by:
                self._update_order_by_for_renamed_attributes(renamed_attrs)

            if self.default_filter:
                self._update_default_filters_for_renamed_attributes(renamed_attrs)

    def _update_default_filters_for_renamed_attributes(self, renamed_attrs: dict[str, str]) -> None:
        for old_name, new_name in renamed_attrs.items():
            if self.default_filter == old_name or self.default_filter.startswith(f"{old_name}__"):
                self.default_filter = new_name + self.default_filter[len(old_name) :]
                break

    def _update_order_by_for_renamed_attributes(self, renamed_attrs: dict[str, str]) -> None:
        updated_order_by = []
        for path in self.order_by:
            updated_path = path
            for old_name, new_name in renamed_attrs.items():
                if path == old_name or path.startswith(f"{old_name}__"):
                    updated_path = new_name + path[len(old_name) :]
                    break
            updated_order_by.append(updated_path)
        self.order_by = updated_order_by

    def _update_hfid_for_renamed_attributes(self, renamed_attrs: dict[str, str]) -> None:
        updated_hfid = []
        for path in self.human_friendly_id:
            updated_path = path
            for old_name, new_name in renamed_attrs.items():
                if path == old_name or path.startswith(f"{old_name}__"):
                    updated_path = new_name + path[len(old_name) :]
                    break
            updated_hfid.append(updated_path)
        self.human_friendly_id = updated_hfid

    def _update_uniqueness_constraints_for_renamed_attributes(self, renamed_attrs: dict[str, str]) -> None:
        updated_constraints = []
        for constraint_paths in self.uniqueness_constraints:
            updated_paths = []
            for path in constraint_paths:
                updated_path = path
                for old_name, new_name in renamed_attrs.items():
                    if path == old_name or path.startswith(f"{old_name}__"):
                        updated_path = new_name + path[len(old_name) :]
                        break
                updated_paths.append(updated_path)
            updated_constraints.append(updated_paths)
        self.uniqueness_constraints = updated_constraints

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
