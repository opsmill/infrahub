from pydantic import BaseModel

from . import core_models, internal_schema

INTERNAL_SCHEMA_NODE_KINDS = [node["namespace"] + node["name"] for node in internal_schema["nodes"]]

CORE_SCHEMA_NODE_KINDS = [node["namespace"] + node["name"] for node in core_models["nodes"] + core_models["generics"]]

SUPPORTED_SCHEMA_EXTENSION_TYPE = ["NodeExtensionSchema"]

IGNORE_FOR_NODE = {"id", "state", "filters", "relationships", "attributes"}


class SchemaNamespace(BaseModel):
    name: str
    user_editable: bool
