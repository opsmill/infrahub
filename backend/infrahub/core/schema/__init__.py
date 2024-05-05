from __future__ import annotations

import uuid
from typing import Any, List, Optional, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.constants import RESTRICTED_NAMESPACES
from infrahub.core.models import HashableModel

from .attribute_schema import AttributeSchema
from .basenode_schema import AttributePathParsingError, BaseNodeSchema, SchemaAttributePath, SchemaAttributePathValue
from .definitions.core import core_models
from .definitions.internal import internal
from .dropdown import DropdownChoice
from .filter import FilterSchema
from .generic_schema import GenericSchema
from .node_schema import NodeSchema
from .profile_schema import ProfileSchema
from .relationship_schema import RelationshipSchema

MainSchemaTypes: TypeAlias = Union[NodeSchema, GenericSchema, ProfileSchema]


# -----------------------------------------------------
# Extensions
#  For the initial implementation its possible to add attribute and relationships on Node
#  Later on we'll consider adding support for other Node attributes like inherited_from etc ...
#  And we'll look into adding support for Generic as well
class BaseNodeExtensionSchema(HashableModel):
    kind: str
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)


class NodeExtensionSchema(BaseNodeExtensionSchema):
    pass


class SchemaExtension(HashableModel):
    nodes: List[NodeExtensionSchema] = Field(default_factory=list)


class SchemaRoot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Optional[str] = Field(default=None)
    generics: List[GenericSchema] = Field(default_factory=list)
    nodes: List[NodeSchema] = Field(default_factory=list)
    extensions: SchemaExtension = SchemaExtension()

    @classmethod
    def has_schema(cls, values: dict[str, Any], name: str) -> bool:
        """Check if a schema exist locally as a node or as a generic."""

        available_schemas = [item.kind for item in values.get("nodes", []) + values.get("generics", [])]
        if name not in available_schemas:
            return False

        return True

    def validate_namespaces(self) -> List[str]:
        models = self.nodes + self.generics
        errors: List[str] = []
        for model in models:
            if model.namespace in RESTRICTED_NAMESPACES:
                errors.append(f"Restricted namespace '{model.namespace}' used on '{model.name}'")

        return errors

    def generate_uuid(self) -> None:
        """Generate UUID for all nodes, attributes & relationships
        Mainly useful during unit tests."""
        for node in self.nodes + self.generics:
            if not node.id:
                node.id = str(uuid.uuid4())
            for item in node.relationships + node.attributes:
                if not item.id:
                    item.id = str(uuid.uuid4())


internal_schema = internal.to_dict()

__all__ = [
    "core_models",
    "internal_schema",
    "AttributePathParsingError",
    "AttributeSchema",
    "BaseNodeSchema",
    "DropdownChoice",
    "FilterSchema",
    "NodeSchema",
    "GenericSchema",
    "ProfileSchema",
    "RelationshipSchema",
    "SchemaAttributePath",
    "SchemaAttributePathValue",
    "SchemaRoot",
    "MainSchemaTypes",
]
