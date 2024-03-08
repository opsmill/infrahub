from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core import registry

from .attribute_schema import AttributeSchema
from .generated.node_schema import GeneratedNodeSchema
from .generic_schema import GenericSchema
from .relationship_schema import RelationshipSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


class NodeSchema(GeneratedNodeSchema):
    def inherit_from_interface(self, interface: GenericSchema) -> None:
        existing_inherited_attributes = {item.name: idx for idx, item in enumerate(self.attributes) if item.inherited}
        existing_inherited_relationships = {
            item.name: idx for idx, item in enumerate(self.relationships) if item.inherited
        }
        existing_inherited_fields = list(existing_inherited_attributes.keys()) + list(
            existing_inherited_relationships.keys()
        )

        for item in interface.attributes + interface.relationships:
            if item.name in self.valid_input_names:
                continue

            new_item = item.duplicate()
            new_item.inherited = True

            if isinstance(item, AttributeSchema) and item.name not in existing_inherited_fields:
                self.attributes.append(new_item)
            elif isinstance(item, AttributeSchema) and item.name in existing_inherited_fields:
                item_idx = existing_inherited_attributes[item.name]
                self.attributes[item_idx] = new_item
            elif isinstance(item, RelationshipSchema) and item.name not in existing_inherited_fields:
                self.relationships.append(new_item)
            elif isinstance(item, RelationshipSchema) and item.name in existing_inherited_fields:
                item_idx = existing_inherited_relationships[item.name]
                self.relationships[item_idx] = new_item

    def get_hierarchy_schema(self, branch: Optional[Union[Branch, str]] = None) -> GenericSchema:
        schema = registry.schema.get(name=self.hierarchy, branch=branch)
        if not isinstance(schema, GenericSchema):
            raise TypeError
        return schema
