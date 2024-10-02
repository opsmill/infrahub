from pydantic import BaseModel

from infrahub.core.constants import (
    FilterSchemaKind,
)

from . import internal_schema

INTERNAL_SCHEMA_NODE_KINDS = [node["namespace"] + node["name"] for node in internal_schema["nodes"]]

SUPPORTED_SCHEMA_EXTENSION_TYPE = ["NodeExtensionSchema"]

KIND_FILTER_MAP = {
    "Text": FilterSchemaKind.TEXT,
    "String": FilterSchemaKind.TEXT,
    "Number": FilterSchemaKind.NUMBER,
    "Integer": FilterSchemaKind.NUMBER,
    "Boolean": FilterSchemaKind.BOOLEAN,
    "Checkbox": FilterSchemaKind.BOOLEAN,
    "Dropdown": FilterSchemaKind.TEXT,
}

IGNORE_FOR_NODE = {"id", "state", "filters", "relationships", "attributes"}


class SchemaNamespace(BaseModel):
    name: str
    user_editable: bool
