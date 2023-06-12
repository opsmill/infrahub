from typing import List
from infrahub_sync import SyncConfig, SchemaMappingModel
from infrahub_client import NodeSchema


def filter_get_identifier(node: NodeSchema, config: SyncConfig) -> List[str]:
    identifiers = [
        attr.name
        for attr in node.attributes
        if attr.unique and filter_has_field(config, name=node.name, field=attr.name)
    ]
    if not identifiers:
        return None
    return identifiers


def filter_get_attributes(node: NodeSchema, config: SyncConfig):
    attributes = [
        attr.name
        for attr in node.attributes
        if not attr.unique and filter_has_field(config, name=node.name, field=attr.name)
    ]

    if not attributes:
        return None

    return attributes


def filter_list_to_set(items: List[str]) -> str:
    """Convert a list in a string representation of a Set."""
    if not items:
        return "None"

    response = '"' + '", "'.join(items) + '"'
    if len(items) == 1:
        response += ","

    return "(" + response + ")"


def filter_list_to_str(items: List[str]) -> str:
    """Convert a list into a string"""
    return ", ".join(items)


def filter_has_node(config: SyncConfig, name: str) -> bool:
    for item in config.schema_mapping:
        if item.name == name:
            return True
    return False


def filter_has_field(config: SyncConfig, name: str, field: str) -> bool:
    for item in config.schema_mapping:
        if item.name == name:
            for subitem in item.fields:
                if subitem.name == field:
                    return True
    return False
