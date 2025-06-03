from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from types import GenericAlias
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

from infrahub.core.constants import (
    DEFAULT_DESCRIPTION_LENGTH,
    DEFAULT_KIND_MAX_LENGTH,
    DEFAULT_KIND_MIN_LENGTH,
    DEFAULT_LABEL_MAX_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    DEFAULT_NAME_MIN_LENGTH,
    DEFAULT_REL_IDENTIFIER_LENGTH,
    NAME_REGEX,
    NAME_REGEX_OR_EMPTY,
    NAMESPACE_REGEX,
    NODE_KIND_REGEX,
    NODE_NAME_REGEX,
    AllowOverrideType,
    BranchSupportType,
    HashableModelState,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipDirection,
    RelationshipKind,
    UpdateSupport,
)
from infrahub.core.schema.attribute_parameters import (
    AttributeParameters,
    NumberAttributeParameters,
    NumberPoolParameters,
    TextAttributeParameters,
)
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.types import ATTRIBUTE_KIND_LABELS


class ExtraField(TypedDict):
    update: UpdateSupport


class SchemaAttribute(BaseModel):
    name: str
    kind: str
    description: str
    extra: ExtraField
    internal_kind: type[Any] | GenericAlias | list[type[Any]] | None = None
    regex: str | None = None
    unique: bool | None = None
    optional: bool | None = None
    min_length: int | None = None
    max_length: int | None = None
    enum: list[str] | None = None
    default_value: Any | None = None
    default_factory: str | None = None
    default_to_none: bool = False
    override_default_value: Any | None = Field(
        default=None,
        description="Currently optional is defined with different defaults for the Pydantic models compared to the internal_schema dictionary",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_dict(self) -> dict[str, Any]:
        model = self.model_dump(
            exclude_none=True,
            exclude={"default_factory", "default_to_none", "extra", "internal_kind", "override_default_value"},
        )
        if self.default_value is not None and isinstance(self.default_value, Enum):
            model["default_value"] = self.default_value.value

        return model

    @property
    def optional_in_model(self) -> bool:
        if (self.optional and self.default_value is None and self.default_factory is None) or self.default_to_none:
            return True

        return False

    @property
    def type_annotation(self) -> str:
        if self.optional_in_model:
            return f"{self.object_kind} | None"

        return self.object_kind

    @property
    def object_kind(self) -> str:
        if isinstance(self.internal_kind, GenericAlias):
            return str(self.internal_kind)

        if isinstance(self.internal_kind, list):
            return " | ".join([internal_kind.__name__ for internal_kind in self.internal_kind])

        if self.internal_kind and self.kind == "List":
            return f"list[{self.internal_kind.__name__}]"

        if self.internal_kind:
            return self.internal_kind.__name__

        kind_map = {
            "Any": "Any",
            "Boolean": "bool",
            "Text": "str",
            "List": "list",
            "Number": "int",
            "URL": "str",
        }
        return kind_map[self.kind]

    @property
    def default_definition(self) -> str:
        if self.default_factory:
            return f"default_factory={self.default_factory}"
        if not self.optional and self.default_value is None:
            return "..."

        if self.override_default_value is not None:
            return f"default={self.override_default_value}"

        formatted_default = self.default_value
        if isinstance(self.default_value, str) and not isinstance(self.default_value, Enum):
            formatted_default = f'"{formatted_default}"'
        elif self.default_to_none:
            formatted_default = None

        return f"default={formatted_default}"

    @property
    def pattern(self) -> str:
        if self.regex:
            return f"pattern='{self.regex}',"
        return ""

    @property
    def min(self) -> str:
        if self.min_length is not None:
            return f"min_length={self.min_length},"

        return ""

    @property
    def max(self) -> str:
        if self.max_length is not None:
            return f"max_length={self.max_length},"

        return ""


class SchemaRelationship(BaseModel):
    name: str
    peer: str
    description: str | None = None
    kind: str | None = None
    identifier: str
    cardinality: str
    branch: str
    optional: bool

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class SchemaNode(BaseModel):
    name: str
    namespace: str
    branch: str
    include_in_menu: bool
    default_filter: str | None = None
    attributes: list[SchemaAttribute]
    relationships: list[SchemaRelationship]
    display_labels: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "branch": self.branch,
            "default_filter": self.default_filter,
            "include_in_menu": self.include_in_menu,
            "attributes": [
                attribute.to_dict()
                for attribute in self.attributes
                if attribute.name not in ["id", "attributes", "relationships"]
            ],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
            "display_labels": self.display_labels,
        }

    def without_duplicates(self, other: SchemaNode) -> SchemaNode:
        schema = deepcopy(self)
        schema.attributes = []
        for attribute in self.attributes:
            if attribute not in other.attributes:
                schema.attributes.append(attribute)

        return schema


@dataclass
class InternalSchema:
    version: str | None
    nodes: list[SchemaNode]

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "nodes": [node.to_dict() for node in self.nodes]}


base_node_schema = SchemaNode(
    name="BaseNode",
    namespace="Schema",
    branch=BranchSupportType.AWARE.value,
    include_in_menu=False,
    default_filter="name__value",
    display_labels=["label__value"],
    attributes=[
        SchemaAttribute(
            name="id",
            description="The ID of the node",
            kind="Text",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="name",
            kind="Text",
            description="Node name, must be unique within a namespace and must start with an uppercase letter.",
            unique=True,
            regex=str(NODE_NAME_REGEX),
            min_length=DEFAULT_NAME_MIN_LENGTH,
            max_length=DEFAULT_NAME_MAX_LENGTH,
            extra={"update": UpdateSupport.MIGRATION_REQUIRED},
        ),
        SchemaAttribute(
            name="namespace",
            kind="Text",
            description="Node Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions.",
            regex=str(NAMESPACE_REGEX),
            min_length=DEFAULT_KIND_MIN_LENGTH,
            max_length=DEFAULT_KIND_MAX_LENGTH,
            extra={"update": UpdateSupport.MIGRATION_REQUIRED},
        ),
        SchemaAttribute(
            name="description",
            kind="Text",
            description="Short description of the model, will be visible in the frontend.",
            optional=True,
            max_length=DEFAULT_DESCRIPTION_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="label",
            kind="Text",
            description="Human friendly representation of the name/kind",
            optional=True,
            max_length=DEFAULT_LABEL_MAX_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="branch",
            kind="Text",
            internal_kind=BranchSupportType,
            description="Type of branch support for the model.",
            enum=BranchSupportType.available_types(),
            default_value=BranchSupportType.AWARE,
            optional=True,
            extra={"update": UpdateSupport.NOT_SUPPORTED},  # https://github.com/opsmill/infrahub/issues/2477
        ),
        SchemaAttribute(
            name="default_filter",
            kind="Text",
            regex=str(NAME_REGEX_OR_EMPTY),
            description="Default filter used to search for a node in addition to its ID. (deprecated: please use human_friendly_id instead)",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="human_friendly_id",
            kind="List",
            internal_kind=str,
            description="Human friendly and unique identifier for the object.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="display_labels",
            kind="List",
            internal_kind=str,
            description="List of attributes to use to generate the display label",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="include_in_menu",
            kind="Boolean",
            description="Defines if objects of this kind should be included in the menu.",
            default_value=True,
            default_to_none=True,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="menu_placement",
            kind="Text",
            description="Defines where in the menu this object should be placed.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="icon",
            kind="Text",
            description="Defines the icon to use in the menu. Must be a valid value from the MDI library https://icon-sets.iconify.design/mdi/",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="order_by",
            kind="List",
            internal_kind=str,
            description="List of attributes to use to order the results by default",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="uniqueness_constraints",
            kind="List",
            internal_kind=list[list[str]],
            description="List of multi-element uniqueness constraints that can combine relationships and attributes",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="documentation",
            kind="URL",
            description="Link to a documentation associated with this object, can be internal or external.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="state",
            kind="Text",
            internal_kind=HashableModelState,
            description="Expected state of the node/generic after loading the schema",
            default_value=HashableModelState.PRESENT,
            enum=HashableModelState.available_types(),
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="attributes",
            kind="List",
            internal_kind=AttributeSchema,
            description="Node attributes",
            default_factory="list",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="relationships",
            kind="List",
            internal_kind=RelationshipSchema,
            description="Node Relationships",
            default_factory="list",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
    ],
    relationships=[],
)

node_schema = SchemaNode(
    name="Node",
    namespace="Schema",
    branch=BranchSupportType.AWARE.value,
    include_in_menu=False,
    default_filter="name__value",
    display_labels=["label__value"],
    attributes=base_node_schema.attributes
    + [
        SchemaAttribute(
            name="inherit_from",
            kind="List",
            internal_kind=str,
            default_factory="list",
            description="List of Generic Kind that this node is inheriting from",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="generate_profile",
            kind="Boolean",
            description="Indicate if a profile schema should be generated for this schema",
            default_value=True,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="generate_template",
            kind="Boolean",
            description="Indicate if an object template schema should be generated for this schema",
            default_value=False,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="hierarchy",
            kind="Text",
            description="Internal value to track the name of the Hierarchy, must match the name of a Generic supporting hierarchical mode",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="parent",
            kind="Text",
            description="Expected Kind for the parent node in a Hierarchy, default to the main generic defined if not defined.",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="children",
            kind="Text",
            description="Expected Kind for the children nodes in a Hierarchy, default to the main generic defined if not defined.",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
    ],
    relationships=[
        SchemaRelationship(
            name="attributes",
            peer="SchemaAttribute",
            kind="Component",
            description="List of supported Attributes for the Node.",
            identifier="schema__node__attributes",
            cardinality="many",
            branch=BranchSupportType.AWARE.value,
            optional=True,
        ),
        SchemaRelationship(
            name="relationships",
            peer="SchemaRelationship",
            kind="Component",
            description="List of supported Relationships for the Node.",
            identifier="schema__node__relationships",
            cardinality="many",
            branch=BranchSupportType.AWARE.value,
            optional=True,
        ),
    ],
)

attribute_schema = SchemaNode(
    name="Attribute",
    namespace="Schema",
    branch=BranchSupportType.AWARE.value,
    include_in_menu=False,
    default_filter=None,
    display_labels=["name__value"],
    attributes=[
        SchemaAttribute(
            name="id",
            description="The ID of the attribute",
            kind="Text",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="name",
            description="Attribute name, must be unique within a model and must be all lowercase.",
            kind="Text",
            regex=str(NAME_REGEX),
            min_length=DEFAULT_KIND_MIN_LENGTH,
            max_length=DEFAULT_KIND_MAX_LENGTH,
            extra={"update": UpdateSupport.MIGRATION_REQUIRED},
        ),
        SchemaAttribute(
            name="kind",
            kind="Text",
            description="Defines the type of the attribute.",
            enum=ATTRIBUTE_KIND_LABELS,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="enum",
            kind="List",
            description="Define a list of valid values for the attribute.",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="computed_attribute",
            kind="JSON",
            internal_kind=ComputedAttribute,
            description="Defines how the value of this attribute will be populated.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="choices",
            kind="List",
            internal_kind=DropdownChoice,
            description="Define a list of valid choices for a dropdown attribute.",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="regex",
            kind="Text",
            description="Regex uses to limit the characters allowed in for the attributes. (deprecated: please use parameters.regex instead)",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="max_length",
            kind="Number",
            description="Set a maximum number of characters allowed for a given attribute. (deprecated: please use parameters.max_length instead)",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="min_length",
            kind="Number",
            description="Set a minimum number of characters allowed for a given attribute. (deprecated: please use parameters.min_length instead)",
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="label",
            kind="Text",
            optional=True,
            description="Human friendly representation of the name. Will be autogenerated if not provided",
            max_length=DEFAULT_NAME_MAX_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="description",
            kind="Text",
            optional=True,
            description="Short description of the attribute.",
            max_length=DEFAULT_DESCRIPTION_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="read_only",
            kind="Boolean",
            description="Set the attribute as Read-Only, users won't be able to change its value. "
            "Mainly relevant for internal object.",
            default_value=False,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="unique",
            kind="Boolean",
            description="Indicate if the value of this attribute must be unique in the database for a given model.",
            default_value=False,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="optional",
            kind="Boolean",
            description="Indicate if this attribute is mandatory or optional.",
            default_value=False,
            override_default_value=False,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="branch",
            kind="Text",
            internal_kind=BranchSupportType,
            description="Type of branch support for the attribute, if not defined it will be inherited from the node.",
            enum=BranchSupportType.available_types(),
            optional=True,
            extra={"update": UpdateSupport.NOT_SUPPORTED},  # https://github.com/opsmill/infrahub/issues/2475
        ),
        SchemaAttribute(
            name="order_weight",
            kind="Number",
            description="Number used to order the attribute in the frontend (table and view). Lowest value will be ordered first.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="default_value",
            kind="Any",
            description="Default value of the attribute.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="inherited",
            kind="Boolean",
            default_value=False,
            description="Internal value to indicate if the attribute was inherited from a Generic node.",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="state",
            kind="Text",
            internal_kind=HashableModelState,
            description="Expected state of the attribute after loading the schema",
            default_value=HashableModelState.PRESENT,
            enum=HashableModelState.available_types(),
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="allow_override",
            kind="Text",
            internal_kind=AllowOverrideType,
            description="Type of allowed override for the attribute.",
            enum=AllowOverrideType.available_types(),
            default_value=AllowOverrideType.ANY,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="parameters",
            kind="JSON",
            internal_kind=[
                AttributeParameters,
                TextAttributeParameters,
                NumberAttributeParameters,
                NumberPoolParameters,
            ],
            optional=True,
            description="Extra parameters specific to this kind of attribute",
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
            default_factory="AttributeParameters",
        ),
        SchemaAttribute(
            name="deprecation",
            kind="Text",
            optional=True,
            description="Mark attribute as deprecated and provide a user-friendly message to display",
            max_length=DEFAULT_DESCRIPTION_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
    ],
    relationships=[
        SchemaRelationship(
            name="node",
            peer="SchemaNode",
            kind="Parent",
            identifier="schema__node__attributes",
            cardinality="one",
            branch=BranchSupportType.AWARE.value,
            optional=False,
        )
    ],
)

relationship_schema = SchemaNode(
    name="Relationship",
    namespace="Schema",
    branch=BranchSupportType.AWARE.value,
    include_in_menu=False,
    default_filter=None,
    display_labels=["name__value"],
    attributes=[
        SchemaAttribute(
            name="id",
            description="The ID of the relationship schema",
            kind="Text",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="name",
            kind="Text",
            description="Relationship name, must be unique within a model and must be all lowercase.",
            regex=str(NAME_REGEX),
            min_length=DEFAULT_KIND_MIN_LENGTH,
            max_length=DEFAULT_KIND_MAX_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="peer",
            kind="Text",
            description="Type (kind) of objects supported on the other end of the relationship.",
            regex=str(NODE_KIND_REGEX),
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="kind",
            kind="Text",
            internal_kind=RelationshipKind,
            description="Defines the type of the relationship.",
            enum=RelationshipKind.available_types(),
            default_value=RelationshipKind.GENERIC,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="label",
            kind="Text",
            description="Human friendly representation of the name. Will be autogenerated if not provided",
            optional=True,
            max_length=DEFAULT_NAME_MAX_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="description",
            kind="Text",
            optional=True,
            description="Short description of the relationship.",
            max_length=DEFAULT_DESCRIPTION_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="identifier",
            kind="Text",
            description="Unique identifier of the relationship within a model,"
            " identifiers must match to traverse a relationship on both direction.",
            regex=str(NAME_REGEX),
            max_length=DEFAULT_REL_IDENTIFIER_LENGTH,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="cardinality",
            kind="Text",
            internal_kind=RelationshipCardinality,
            description="Defines how many objects are expected on the other side of the relationship.",
            enum=RelationshipCardinality.available_types(),
            default_value=RelationshipCardinality.MANY,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="min_count",
            kind="Number",
            description="Defines the minimum objects allowed on the other side of the relationship.",
            default_value=0,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="max_count",
            kind="Number",
            description="Defines the maximum objects allowed on the other side of the relationship.",
            default_value=0,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="common_relatives",
            kind="List",
            internal_kind=str,
            optional=True,
            description="List of relationship names on the peer schema for which all objects must share the same set of peers.",
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="order_weight",
            kind="Number",
            description="Number used to order the relationship in the frontend (table and view). Lowest value will be ordered first.",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="optional",
            kind="Boolean",
            description="Indicate if this relationship is mandatory or optional.",
            default_value=False,
            override_default_value=True,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="branch",
            kind="Text",
            internal_kind=BranchSupportType,
            description="Type of branch support for the relatioinship, if not defined it will be determine based both peers.",
            enum=BranchSupportType.available_types(),
            optional=True,
            extra={"update": UpdateSupport.NOT_SUPPORTED},  # https://github.com/opsmill/infrahub/issues/2476
        ),
        SchemaAttribute(
            name="inherited",
            kind="Boolean",
            description="Internal value to indicate if the relationship was inherited from a Generic node.",
            default_value=False,
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="direction",
            kind="Text",
            internal_kind=RelationshipDirection,
            description="Defines the direction of the relationship, "
            " Unidirectional relationship are required when the same model is on both side.",
            enum=RelationshipDirection.available_types(),
            default_value=RelationshipDirection.BIDIR,
            optional=True,
            extra={"update": UpdateSupport.NOT_SUPPORTED},  # https://github.com/opsmill/infrahub/issues/2471
        ),
        SchemaAttribute(
            name="hierarchical",
            kind="Text",
            description="Internal attribute to track the type of hierarchy this relationship is part of, must match a valid Generic Kind",
            optional=True,
            extra={"update": UpdateSupport.NOT_SUPPORTED},  # https://github.com/opsmill/infrahub/issues/2596
        ),
        SchemaAttribute(
            name="state",
            kind="Text",
            internal_kind=HashableModelState,
            description="Expected state of the relationship after loading the schema",
            default_value=HashableModelState.PRESENT,
            enum=HashableModelState.available_types(),
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
        SchemaAttribute(
            name="on_delete",
            kind="Text",
            internal_kind=RelationshipDeleteBehavior,
            description="Default is no-action. If cascade, related node(s) are deleted when this node is deleted.",
            enum=RelationshipDeleteBehavior.available_types(),
            default_value=None,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="allow_override",
            kind="Text",
            internal_kind=AllowOverrideType,
            description="Type of allowed override for the relationship.",
            enum=AllowOverrideType.available_types(),
            default_value=AllowOverrideType.ANY,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="read_only",
            kind="Boolean",
            description="Set the relationship as read-only, users won't be able to change its value.",
            default_value=False,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="deprecation",
            kind="Text",
            optional=True,
            description="Mark relationship as deprecated and provide a user-friendly message to display",
            max_length=DEFAULT_DESCRIPTION_LENGTH,
            extra={"update": UpdateSupport.ALLOWED},
        ),
    ],
    relationships=[
        SchemaRelationship(
            name="node",
            peer="SchemaNode",
            kind="Parent",
            identifier="schema__node__relationships",
            cardinality="one",
            branch=BranchSupportType.AWARE.value,
            optional=False,
        )
    ],
)

generic_schema = SchemaNode(
    name="Generic",
    namespace="Schema",
    branch=BranchSupportType.AWARE.value,
    include_in_menu=False,
    default_filter="name__value",
    display_labels=["label__value"],
    attributes=base_node_schema.attributes
    + [
        SchemaAttribute(
            name="hierarchical",
            kind="Boolean",
            description="Defines if the Generic support the hierarchical mode.",
            optional=True,
            default_value=False,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="generate_profile",
            kind="Boolean",
            description="Indicate if a profile schema should be generated for this schema",
            default_value=True,
            optional=True,
            extra={"update": UpdateSupport.VALIDATE_CONSTRAINT},
        ),
        SchemaAttribute(
            name="generate_template",
            kind="Boolean",
            description="Indicate if an object template schema should be generated for this schema",
            default_value=False,
            optional=True,
            extra={"update": UpdateSupport.ALLOWED},
        ),
        SchemaAttribute(
            name="used_by",
            kind="List",
            internal_kind=str,
            default_factory="list",
            description="List of Nodes that are referencing this Generic",
            optional=True,
            extra={"update": UpdateSupport.NOT_APPLICABLE},
        ),
    ],
    relationships=[
        SchemaRelationship(
            name="attributes",
            peer="SchemaAttribute",
            identifier="schema__node__attributes",
            cardinality="many",
            branch=BranchSupportType.AWARE.value,
            optional=True,
        ),
        SchemaRelationship(
            name="relationships",
            peer="SchemaRelationship",
            identifier="schema__node__relationships",
            cardinality="many",
            branch=BranchSupportType.AWARE.value,
            optional=True,
        ),
    ],
)

internal = InternalSchema(
    version=None,
    nodes=[
        node_schema,
        attribute_schema,
        relationship_schema,
        generic_schema,
    ],
)
