from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import jinja2
from infrahub_sdk import (
    AttributeSchema,
    NodeSchema,
    RelationshipKind,
    RelationshipSchema,
)

from infrahub_sync import SyncConfig
from infrahub_sync.generator.utils import list_to_set, list_to_str

ATTRIBUTE_KIND_MAP = {
    "Text": "str",
    "String": "str",
    "TextArea": "str",
    "DateTime": "str",
    "HashedPassword": "str",
    "Number": "int",
    "Integer": "int",
    "Boolean": "bool",
}


def has_node(config: SyncConfig, name: str) -> bool:
    for item in config.schema_mapping:
        if item.name == name:
            return True
    return False


def has_field(config: SyncConfig, name: str, field: str) -> bool:
    for item in config.schema_mapping:
        if item.name == name:
            for subitem in item.fields:
                if subitem.name == field:
                    return True
    return False


def get_identifiers(node: NodeSchema, config: SyncConfig) -> Optional[List[str]]:
    """Return the identifiers that should be used by DiffSync."""

    config_identifiers = [
        item.identifiers for item in config.schema_mapping if item.name == node.kind and item.identifiers
    ]

    if config_identifiers:
        return config_identifiers[0]

    identifiers = [
        attr.name for attr in node.attributes if attr.unique and has_field(config, name=node.kind, field=attr.name)
    ]

    if not identifiers:
        return None

    return identifiers


def get_attributes(node: NodeSchema, config: SyncConfig) -> Optional[List[str]]:
    """Return the attributes that should be used by DiffSync."""
    attrs_attributes = [
        attr.name for attr in node.attributes if not attr.unique and has_field(config, name=node.kind, field=attr.name)
    ]
    rels_identifiers = [
        rel.name
        for rel in node.relationships
        if rel.kind != RelationshipKind.COMPONENT and has_field(config, name=node.kind, field=rel.name)
    ]

    identifiers = get_identifiers(node=node, config=config)
    if not identifiers:
        return None

    attributes = [item for item in rels_identifiers + attrs_attributes if item not in identifiers]

    if not attributes:
        return None

    return attributes


def get_children(node: NodeSchema, config: SyncConfig) -> Optional[str]:
    # rel.peer.lower() might now work in all cases we should have a better function to convert that
    children = {
        rel.peer.lower(): rel.name
        for rel in node.relationships
        if rel.cardinality == "many"
        and rel.kind == RelationshipKind.COMPONENT
        and has_field(config, name=node.kind, field=rel.name)
    }

    if not children:
        return None

    children_list = [f'"{key}": "{value}"' for key, value in children.items()]
    return "{" + ", ".join(children_list) + "}"


def get_kind(item: Union[RelationshipSchema, AttributeSchema]) -> str:
    kind = "str"
    if isinstance(item, AttributeSchema):
        kind = ATTRIBUTE_KIND_MAP.get(item.kind, "str")
        if item.optional:
            kind = f"Optional[{kind}]"
            if item.default_value is not None:
                kind += f" = {item.default_value}"
            else:
                kind += " = None"

    elif isinstance(item, RelationshipSchema) and item.cardinality == "one":
        if item.optional:
            kind = f"Optional[{kind}] = None"

    elif isinstance(item, RelationshipSchema) and item.cardinality == "many":
        kind = "List[str]"
        if item.optional:
            kind = f"Optional[{kind}]"
        kind += " = []"

    return kind


def has_children(node: NodeSchema, config: SyncConfig) -> bool:
    if get_children(config=config, node=node):
        return True
    return False


def render_template(template_file: Path, output_dir: Path, output_file: Path, context: Dict[str, Any]):
    template_loader = jinja2.PackageLoader("infrahub_sync", "generator/templates")
    template_env = jinja2.Environment(
        loader=template_loader,
    )
    template_env.filters["get_identifiers"] = get_identifiers
    template_env.filters["get_attributes"] = get_attributes
    template_env.filters["get_children"] = get_children
    template_env.filters["list_to_set"] = list_to_set
    template_env.filters["list_to_str"] = list_to_str
    template_env.filters["has_node"] = has_node
    template_env.filters["has_field"] = has_field
    template_env.filters["has_children"] = has_children
    template_env.filters["get_kind"] = get_kind

    template = template_env.get_template(str(template_file))

    rendered_tpl = template.render(**context)  # type: ignore[arg-type]
    output_filename = output_dir / output_file
    output_filename.write_text(rendered_tpl, encoding="utf-8")
