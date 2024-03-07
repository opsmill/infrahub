from __future__ import annotations

import enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field
import hashlib
import keyword
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type, Union

from infrahub_sdk.utils import compare_lists, intersection
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from infrahub.core.constants import RESTRICTED_NAMESPACES
from infrahub.core.models import HashableModel
from infrahub.core.relationship import Relationship
from infrahub.types import ATTRIBUTE_KIND_LABELS

from .attribute_schema import AttributeSchema
from .basenode_schema import AttributePathParsingError, BaseNodeSchema, SchemaAttributePath
from .definitions.core import core_models
from .definitions.internal import internal
from .dropdown import DropdownChoice
from .filter import FilterSchema
from .generic_schema import GenericSchema
from .node_schema import NodeSchema
from .relationship_schema import RelationshipSchema

# pylint: disable=redefined-builtin

# Generate an Enum for Pydantic based on a List of String
attribute_dict = {attr.upper(): attr for attr in ATTRIBUTE_KIND_LABELS}
AttributeKind = enum.Enum("AttributeKind", dict(attribute_dict))

RELATIONSHIPS_MAPPING = {"Relationship": Relationship}


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
    "RelationshipSchema",
    "SchemaAttributePath",
    "SchemaRoot",
]
