from .generic_schema import GenericSchema
from .node_schema import NodeSchema


class NodeInheritanceHandler:
    def inherit_from_interface(self, node: NodeSchema, interface: GenericSchema) -> None:
        existing_inherited_attributes: dict[str, int] = {
            item.name: idx for idx, item in enumerate(node.attributes) if item.inherited
        }
        existing_inherited_relationships: dict[str, int] = {
            item.name: idx for idx, item in enumerate(node.relationships) if item.inherited
        }

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
            if getattr(interface, prop_name) and not getattr(node, prop_name):
                setattr(node, prop_name, getattr(interface, prop_name))

        # Build a mapping from source_attribute_id to (index, old_name) for existing inherited attributes
        # This allows us to detect renamed attributes by their source ID
        existing_inherited_attr_by_source_id: dict[str, tuple[int, str]] = {
            item.source_attribute_id: (idx, item.name)
            for idx, item in enumerate(node.attributes)
            if item.inherited and item.source_attribute_id
        }

        # Track renamed attributes to update schema properties (uniqueness_constraints, etc.)
        renamed_attrs: dict[str, str] = {}  # old_name -> new_name

        for attribute in interface.attributes:
            if attribute.name in node.valid_local_names:
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
                node.attributes[item_idx].update_from_generic(other=new_attribute)
                node.attributes[item_idx].name = new_attribute.name  # Update name explicitly
                node.attributes[item_idx].source_attribute_id = new_attribute.source_attribute_id
            elif attribute.name not in existing_inherited_attributes:
                # New attribute added on the generic
                node.attributes.append(new_attribute)
            else:
                # Existing inherited attribute that has not been renamed
                item_idx = existing_inherited_attributes[attribute.name]
                node.attributes[item_idx].update_from_generic(other=new_attribute)
                node.attributes[item_idx].source_attribute_id = new_attribute.source_attribute_id

        for relationship in interface.relationships:
            if relationship.name in node.valid_local_names:
                continue

            new_relationship = relationship.duplicate()
            new_relationship.id = None
            new_relationship.inherited = True

            if relationship.name not in existing_inherited_relationships:
                node.relationships.append(new_relationship)
            else:
                item_idx = existing_inherited_relationships[relationship.name]
                node.relationships[item_idx].update_from_generic(other=new_relationship)

        if renamed_attrs:
            self._update_uniqueness_constraints_for_renamed_attributes(node=node, renamed_attrs=renamed_attrs)
            self._update_hfid_for_renamed_attributes(node=node, renamed_attrs=renamed_attrs)
            self._update_order_by_for_renamed_attributes(node=node, renamed_attrs=renamed_attrs)
            self._update_default_filters_for_renamed_attributes(node=node, renamed_attrs=renamed_attrs)
            self._update_display_labels_for_renamed_attributes(node=node, renamed_attrs=renamed_attrs)

    def _update_default_filters_for_renamed_attributes(self, node: NodeSchema, renamed_attrs: dict[str, str]) -> None:
        if not node.default_filter:
            return
        for old_name, new_name in renamed_attrs.items():
            if node.default_filter == old_name or node.default_filter.startswith(f"{old_name}__"):
                node.default_filter = new_name + node.default_filter[len(old_name) :]
                break

    def _update_order_by_for_renamed_attributes(self, node: NodeSchema, renamed_attrs: dict[str, str]) -> None:
        if not node.order_by:
            return
        node.order_by = self._get_updated_renamed_attrs_data(attr_data=node.order_by, renamed_attrs=renamed_attrs)

    def _update_hfid_for_renamed_attributes(self, node: NodeSchema, renamed_attrs: dict[str, str]) -> None:
        if not node.human_friendly_id:
            return
        node.human_friendly_id = self._get_updated_renamed_attrs_data(
            attr_data=node.human_friendly_id, renamed_attrs=renamed_attrs
        )

    def _update_display_labels_for_renamed_attributes(self, node: NodeSchema, renamed_attrs: dict[str, str]) -> None:
        if not node.display_labels:
            return
        node.display_labels = self._get_updated_renamed_attrs_data(
            attr_data=node.display_labels, renamed_attrs=renamed_attrs
        )

    def _update_uniqueness_constraints_for_renamed_attributes(
        self, node: NodeSchema, renamed_attrs: dict[str, str]
    ) -> None:
        if not node.uniqueness_constraints:
            return
        updated_constraints = []
        for constraint_paths in node.uniqueness_constraints:
            updated_constraints.append(
                self._get_updated_renamed_attrs_data(attr_data=constraint_paths, renamed_attrs=renamed_attrs)
            )
        node.uniqueness_constraints = updated_constraints

    def _get_updated_renamed_attrs_data(self, attr_data: list[str], renamed_attrs: dict[str, str]) -> list[str]:
        updated_attrs_data = []
        for data in attr_data:
            updated_attr_data = data
            for old_name, new_name in renamed_attrs.items():
                if data == old_name or data.startswith(f"{old_name}__"):
                    updated_attr_data = new_name + data[len(old_name) :]
                    break
            updated_attrs_data.append(updated_attr_data)
        return updated_attrs_data
