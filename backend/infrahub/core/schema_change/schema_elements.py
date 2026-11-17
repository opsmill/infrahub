from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema_change.constants import SCHEMA_PROPERTY_PATH_SEPARATOR, SchemaOperationSection

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, NodeExtensionSchema, RelationshipSchema
    from infrahub.core.schema.basenode_schema import BaseNodeSchema

    type ElementHolder = BaseNodeSchema | NodeExtensionSchema


def section_elements(
    *, node: ElementHolder, section: SchemaOperationSection
) -> list[AttributeSchema] | list[RelationshipSchema]:
    """Return the list that holds the attributes or the relationships of a kind, not a copy of it."""
    match section:
        case SchemaOperationSection.ATTRIBUTES:
            return node.attributes
        case SchemaOperationSection.RELATIONSHIPS:
            return node.relationships


def find_element(
    *, node: ElementHolder, section: SchemaOperationSection, name: str
) -> AttributeSchema | RelationshipSchema | None:
    for element in section_elements(node=node, section=section):
        if element.name == name:
            return element
    return None


def find_element_by_id(
    *, node: ElementHolder, section: SchemaOperationSection, element_id: str
) -> AttributeSchema | RelationshipSchema | None:
    for element in section_elements(node=node, section=section):
        if element.id == element_id:
            return element
    return None


def split_property_path(property_name: str) -> list[str]:
    return property_name.split(SCHEMA_PROPERTY_PATH_SEPARATOR)


def read_property(*, holder: object, property_name: str) -> object:
    """Return the value at a dotted property path, or `None` when a level of the path is `None`."""
    value: object = holder
    for part in split_property_path(property_name):
        if value is None:
            return None
        value = getattr(value, part)
    return value
