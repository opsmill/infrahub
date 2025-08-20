from pydantic import BaseModel

from . import internal_schema

INTERNAL_SCHEMA_NODE_KINDS = [node["namespace"] + node["name"] for node in internal_schema["nodes"]]

SUPPORTED_SCHEMA_EXTENSION_TYPE = ["NodeExtensionSchema"]

IGNORE_FOR_NODE = {"id", "state", "filters", "relationships", "attributes"}


class SchemaNamespace(BaseModel):
    name: str
    user_editable: bool
