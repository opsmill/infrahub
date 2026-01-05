from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from infrahub_sdk.utils import deep_merge_dict
from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.constants import RESTRICTED_NAMESPACES
from infrahub.core.models import HashableModel
from infrahub.exceptions import SchemaNotFoundError

from .attribute_schema import AttributeSchema
from .basenode_schema import AttributePathParsingError, BaseNodeSchema, SchemaAttributePath, SchemaAttributePathValue
from .definitions.core import core_models
from .definitions.internal import internal
from .dropdown import DropdownChoice
from .generic_schema import GenericSchema
from .node_schema import NodeSchema
from .profile_schema import ProfileSchema
from .relationship_schema import RelationshipSchema
from .template_schema import TemplateSchema

NonGenericSchemaTypes = NodeSchema | ProfileSchema | TemplateSchema
MainSchemaTypes = NonGenericSchemaTypes | GenericSchema


# -----------------------------------------------------
# Extensions
#  For the initial implementation its possible to add attribute and relationships on Node
#  Later on we'll consider adding support for other Node attributes like inherited_from etc ...
#  And we'll look into adding support for Generic as well
class BaseNodeExtensionSchema(HashableModel):
    kind: str
    attributes: list[AttributeSchema] = Field(default_factory=list)
    relationships: list[RelationshipSchema] = Field(default_factory=list)


class NodeExtensionSchema(BaseNodeExtensionSchema):
    pass


class SchemaExtension(HashableModel):
    nodes: list[NodeExtensionSchema] = Field(default_factory=list)


class SchemaWarningType(Enum):
    DEPRECATION = "deprecation"


class SchemaWarningKind(BaseModel):
    kind: str = Field(..., description="The kind impacted by the warning")
    field: str | None = Field(default=None, description="The attribute or relationship impacted by the warning")


class SchemaWarning(BaseModel):
    type: SchemaWarningType = Field(..., description="The type of warning")
    kinds: list[SchemaWarningKind] = Field(default_factory=list, description="The kinds impacted by the warning")
    message: str = Field(..., description="The message that describes the warning")


class SchemaRoot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str | None = Field(default=None)
    generics: list[GenericSchema] = Field(default_factory=list)
    nodes: list[NodeSchema] = Field(default_factory=list)
    extensions: SchemaExtension = SchemaExtension()

    @classmethod
    def has_schema(cls, values: dict[str, Any], name: str) -> bool:
        """Check if a schema exist locally as a node or as a generic."""

        available_schemas = [item.kind for item in values.get("nodes", []) + values.get("generics", [])]
        if name not in available_schemas:
            return False

        return True

    def get(self, name: str) -> NodeSchema | GenericSchema:
        """Check if a schema exist locally as a node or as a generic."""

        for item in self.nodes + self.generics:
            if item.kind == name:
                return item

        raise SchemaNotFoundError(branch_name="undefined", identifier=name)

    def validate_namespaces(self) -> list[str]:
        models = self.nodes + self.generics
        errors: list[str] = []
        for model in models:
            if model.namespace in RESTRICTED_NAMESPACES:
                errors.append(f"Restricted namespace '{model.namespace}' used on '{model.name}'")

        return errors

    def gather_warnings(self) -> list[SchemaWarning]:
        models = self.nodes + self.generics
        warnings: list[SchemaWarning] = []
        for model in models:
            if model.display_labels is not None:
                warnings.append(
                    SchemaWarning(
                        type=SchemaWarningType.DEPRECATION,
                        kinds=[SchemaWarningKind(kind=model.kind)],
                        message="display_labels are deprecated, use display_label instead",
                    )
                )
            if model.default_filter is not None:
                warnings.append(
                    SchemaWarning(
                        type=SchemaWarningType.DEPRECATION,
                        kinds=[SchemaWarningKind(kind=model.kind)],
                        message="default_filter is deprecated",
                    )
                )
            for attribute in model.attributes:
                if attribute.max_length is not None:
                    warnings.append(
                        SchemaWarning(
                            type=SchemaWarningType.DEPRECATION,
                            kinds=[SchemaWarningKind(kind=model.kind, field=attribute.name)],
                            message="Use of 'max_length' on attributes is deprecated, use parameters instead",
                        )
                    )
                if attribute.min_length is not None:
                    warnings.append(
                        SchemaWarning(
                            type=SchemaWarningType.DEPRECATION,
                            kinds=[SchemaWarningKind(kind=model.kind, field=attribute.name)],
                            message="Use of 'min_length' on attributes is deprecated, use parameters instead",
                        )
                    )

        return warnings

    def generate_uuid(self) -> None:
        """Generate UUID for all nodes, attributes & relationships
        Mainly useful during unit tests."""
        for node in self.nodes + self.generics:
            if not node.id:
                node.id = str(uuid.uuid4())
            for item in node.relationships + node.attributes:
                if not item.id:
                    item.id = str(uuid.uuid4())

    def merge(self, schema: SchemaRoot) -> SchemaRoot:
        """Return a new `SchemaRoot` after merging `self` with `schema`."""
        return SchemaRoot.model_validate(deep_merge_dict(dicta=self.model_dump(), dictb=schema.model_dump()))

    def duplicate(self) -> SchemaRoot:
        """Return a duplicate of the current schema."""
        return SchemaRoot.model_validate(self.model_dump())


internal_schema = internal.to_dict()

__all__ = [
    "AttributePathParsingError",
    "AttributeSchema",
    "BaseNodeSchema",
    "DropdownChoice",
    "GenericSchema",
    "MainSchemaTypes",
    "NodeSchema",
    "ProfileSchema",
    "RelationshipSchema",
    "SchemaAttributePath",
    "SchemaAttributePathValue",
    "SchemaRoot",
    "TemplateSchema",
    "core_models",
    "internal_schema",
]
