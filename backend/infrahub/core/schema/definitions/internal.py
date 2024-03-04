from copy import copy
from dataclasses import dataclass
from typing import Any, NotRequired, Optional, TypedDict, cast

from infrahub.core.constants import (
    DEFAULT_DESCRIPTION_LENGTH,
    DEFAULT_KIND_MAX_LENGTH,
    DEFAULT_KIND_MIN_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    DEFAULT_NAME_MIN_LENGTH,
    DEFAULT_REL_IDENTIFIER_LENGTH,
    NAME_REGEX,
    NAMESPACE_REGEX,
    NODE_KIND_REGEX,
    NODE_NAME_REGEX,
    BranchSupportType,
    RelationshipCardinality,
    RelationshipDirection,
    RelationshipKind,
    UpdateSupport,
)
from infrahub.types import ATTRIBUTE_KIND_LABELS


class ExtraField(TypedDict):
    update: Optional[UpdateSupport]


class SchemaAttribute(TypedDict):
    name: str
    kind: str
    description: str
    regex: NotRequired[str]
    unique: NotRequired[bool]
    optional: NotRequired[bool]
    min_length: NotRequired[int]
    max_length: NotRequired[int]
    enum: NotRequired[list[str]]
    default_value: NotRequired[Any]
    extra: ExtraField


class SchemaRelationship(TypedDict):
    name: str
    peer: str
    description: NotRequired[Optional[str]]
    kind: NotRequired[Optional[str]]
    identifier: str
    cardinality: str
    branch: str
    optional: bool


class SchemaNode(TypedDict):
    name: str
    namespace: str
    branch: str
    include_in_menu: bool
    default_filter: NotRequired[Optional[str]]
    attributes: list[SchemaAttribute]
    relationships: list[SchemaRelationship]
    display_labels: NotRequired[list[str]]


@dataclass
class InternalSchema:
    version: Optional[str]
    nodes: list[SchemaNode]

    def to_dict(self) -> dict[str, Any]:
        nodes = cast(list[dict[str, Any]], copy(self.nodes))
        for node in nodes:
            for attribute in node["attributes"]:
                attribute.pop("extra")
        return {"version": self.version, "nodes": nodes}


node_schema: SchemaNode = {
    "name": "Node",
    "namespace": "Schema",
    "branch": BranchSupportType.AWARE.value,
    "include_in_menu": False,
    "default_filter": "name__value",
    "display_labels": ["label__value"],
    "attributes": [
        {
            "name": "name",
            "kind": "Text",
            "description": "Node name, must be unique within a namespace and must start with an uppercase letter.",
            "unique": True,
            "regex": str(NODE_NAME_REGEX),
            "min_length": DEFAULT_NAME_MIN_LENGTH,
            "max_length": DEFAULT_NAME_MAX_LENGTH,
            "extra": {"update": UpdateSupport.NOT_SUPPORTED},
        },
        {
            "name": "namespace",
            "kind": "Text",
            "description": "Node Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions.",
            "regex": str(NAMESPACE_REGEX),
            "min_length": DEFAULT_KIND_MIN_LENGTH,
            "max_length": DEFAULT_KIND_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "label",
            "kind": "Text",
            "description": "Human friendly representation of the name/kind",
            "optional": True,
            "max_length": DEFAULT_NAME_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "description",
            "kind": "Text",
            "description": "Short description of the model, will be visible in the frontend.",
            "optional": True,
            "max_length": DEFAULT_DESCRIPTION_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "branch",
            "kind": "Text",
            "description": "Type of branch support for the model.",
            "enum": BranchSupportType.available_types(),
            "default_value": BranchSupportType.AWARE.value,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "default_filter",
            "kind": "Text",
            "regex": str(NAME_REGEX),
            "description": "Default filter used to search for a node in addition to its ID.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "display_labels",
            "kind": "List",
            "description": "List of attributes to use to generate the display label",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "include_in_menu",
            "kind": "Boolean",
            "description": "Defines if objects of this kind should be included in the menu.",
            "default_value": True,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "menu_placement",
            "kind": "Text",
            "description": "Defines where in the menu this object should be placed.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "icon",
            "kind": "Text",
            "description": "Defines the icon to use in the menu. Must be a valid value from the MDI library https://icon-sets.iconify.design/mdi/",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "order_by",
            "kind": "List",
            "description": "List of attributes to use to order the results by default",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "inherit_from",
            "kind": "List",
            "description": "List of Generic Kind that this node is inheriting from",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "hierarchy",
            "kind": "Text",
            "description": "Internal value to track the name of the Hierarchy, must match the name of a Generic supporting hierarchical mode",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "parent",
            "kind": "Text",
            "description": "Expected Kind for the parent node in a Hierarchy, default to the main generic defined if not defined.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "children",
            "kind": "Text",
            "description": "Expected Kind for the children nodes in a Hierarchy, default to the main generic defined if not defined.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "uniqueness_constraints",
            "kind": "List",
            "description": "List of multi-element uniqueness constraints that can combine relationships and attributes",
            "optional": True,
            "extra": {"update": None},
        },
    ],
    "relationships": [
        {
            "name": "attributes",
            "peer": "SchemaAttribute",
            "kind": "Component",
            "description": "List of supported Attributes for the Node.",
            "identifier": "schema__node__attributes",
            "cardinality": "many",
            "branch": BranchSupportType.AWARE.value,
            "optional": True,
        },
        {
            "name": "relationships",
            "peer": "SchemaRelationship",
            "kind": "Component",
            "description": "List of supported Relationships for the Node.",
            "identifier": "schema__node__relationships",
            "cardinality": "many",
            "branch": BranchSupportType.AWARE.value,
            "optional": True,
        },
    ],
}

attribute_schema: SchemaNode = {
    "name": "Attribute",
    "namespace": "Schema",
    "branch": BranchSupportType.AWARE.value,
    "include_in_menu": False,
    "default_filter": None,
    "display_labels": ["name__value"],
    "attributes": [
        {
            "name": "name",
            "description": "Attribute name, must be unique within a model and must be all lowercase.",
            "kind": "Text",
            "regex": str(NAME_REGEX),
            "min_length": DEFAULT_KIND_MIN_LENGTH,
            "max_length": DEFAULT_KIND_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "kind",
            "kind": "Text",
            "description": "Defines the type of the attribute.",
            "enum": ATTRIBUTE_KIND_LABELS,
            "extra": {"update": None},
        },
        {
            "name": "enum",
            "kind": "List",
            "description": "Define a list of valid values for the attribute.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "choices",
            "kind": "List",
            "description": "Define a list of valid choices for a dropdown attribute.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "regex",
            "kind": "Text",
            "description": "Regex uses to limit limit the characters allowed in for the attributes.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "max_length",
            "kind": "Number",
            "description": "Set a maximum number of characters allowed for a given attribute.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "min_length",
            "kind": "Number",
            "description": "Set a minimum number of characters allowed for a given attribute.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "label",
            "kind": "Text",
            "optional": True,
            "description": "Human friendly representation of the name. Will be autogenerated if not provided",
            "max_length": DEFAULT_NAME_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "description",
            "kind": "Text",
            "optional": True,
            "description": "Short description of the attribute.",
            "max_length": DEFAULT_DESCRIPTION_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "read_only",
            "kind": "Boolean",
            "description": "Set the attribute as Read-Only, users won't be able to change its value. "
            "Mainly relevant for internal object.",
            "default_value": False,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "unique",
            "kind": "Boolean",
            "description": "Indicate if the value of this attribute must be unique in the database for a given model.",
            "default_value": False,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "optional",
            "kind": "Boolean",
            "description": "Indicate if this attribute is mandatory or optional.",
            "default_value": True,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "branch",
            "kind": "Text",
            "description": "Type of branch support for the attribute, if not defined it will be inherited from the node.",
            "enum": BranchSupportType.available_types(),
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "order_weight",
            "kind": "Number",
            "description": "Number used to order the attribute in the frontend (table and view).",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "default_value",
            "kind": "Any",
            "description": "Default value of the attribute.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "inherited",
            "kind": "Boolean",
            "default_value": False,
            "description": "Internal value to indicate if the attribute was inherited from a Generic node.",
            "optional": True,
            "extra": {"update": None},
        },
    ],
    "relationships": [
        {
            "name": "node",
            "peer": "SchemaNode",
            "kind": "Parent",
            "identifier": "schema__node__attributes",
            "cardinality": "one",
            "branch": BranchSupportType.AWARE.value,
            "optional": False,
        }
    ],
}

relationship_schema: SchemaNode = {
    "name": "Relationship",
    "namespace": "Schema",
    "branch": BranchSupportType.AWARE.value,
    "include_in_menu": False,
    "default_filter": None,
    "display_labels": ["name__value"],
    "attributes": [
        {
            "name": "name",
            "kind": "Text",
            "description": "Relationship name, must be unique within a model and must be all lowercase.",
            "regex": str(NAME_REGEX),
            "min_length": DEFAULT_KIND_MIN_LENGTH,
            "max_length": DEFAULT_KIND_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "peer",
            "kind": "Text",
            "description": "Type (kind) of objects supported on the other end of the relationship.",
            "regex": str(NODE_KIND_REGEX),
            "min_length": DEFAULT_KIND_MIN_LENGTH,
            "max_length": DEFAULT_KIND_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "kind",
            "kind": "Text",
            "description": "Defines the type of the relationship.",
            "enum": RelationshipKind.available_types(),
            "default_value": RelationshipKind.GENERIC.value,
            "extra": {"update": None},
        },
        {
            "name": "label",
            "kind": "Text",
            "description": "Human friendly representation of the name. Will be autogenerated if not provided",
            "optional": True,
            "max_length": DEFAULT_NAME_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "description",
            "kind": "Text",
            "optional": True,
            "description": "Short description of the relationship.",
            "max_length": DEFAULT_DESCRIPTION_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "identifier",
            "kind": "Text",
            "description": "Unique identifier of the relationship within a model,"
            " identifiers must match to traverse a relationship on both direction.",
            "regex": str(NAME_REGEX),
            "max_length": DEFAULT_REL_IDENTIFIER_LENGTH,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "cardinality",
            "kind": "Text",
            "description": "Defines how many objects are expected on the other side of the relationship.",
            "enum": RelationshipCardinality.available_types(),
            "default_value": RelationshipCardinality.MANY.value,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "min_count",
            "kind": "Number",
            "description": "Defines the minimum objects allowed on the other side of the relationship.",
            "default_value": 0,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "max_count",
            "kind": "Number",
            "description": "Defines the maximum objects allowed on the other side of the relationship.",
            "default_value": 0,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "order_weight",
            "kind": "Number",
            "description": "Number used to order the relationship in the frontend (table and view).",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "optional",
            "kind": "Boolean",
            "description": "Indicate if this relationship is mandatory or optional.",
            "default_value": False,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "branch",
            "kind": "Text",
            "description": "Type of branch support for the relatioinship, if not defined it will be determine based both peers.",
            "enum": BranchSupportType.available_types(),
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "inherited",
            "kind": "Boolean",
            "description": "Internal value to indicate if the relationship was inherited from a Generic node.",
            "default_value": False,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "direction",
            "kind": "Text",
            "description": "Defines the direction of the relationship, "
            " Unidirectional relationship are required when the same model is on both side.",
            "enum": RelationshipDirection.available_types(),
            "default_value": RelationshipDirection.BIDIR.value,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "hierarchical",
            "kind": "Text",
            "description": "Internal attribute to track the type of hierarchy this relationship is part of, must match a valid Generic Kind",
            "optional": True,
            "extra": {"update": None},
        },
    ],
    "relationships": [
        {
            "name": "node",
            "peer": "SchemaNode",
            "kind": "Parent",
            "identifier": "schema__node__relationships",
            "cardinality": "one",
            "branch": BranchSupportType.AWARE.value,
            "optional": False,
        }
    ],
}

generic_schema: SchemaNode = {
    "name": "Generic",
    "namespace": "Schema",
    "branch": BranchSupportType.AWARE.value,
    "include_in_menu": False,
    "default_filter": "name__value",
    "display_labels": ["label__value"],
    "attributes": [
        {
            "name": "name",
            "kind": "Text",
            "description": "Generic name, must be unique within a namespace and must start with an uppercase letter.",
            "unique": True,
            "regex": str(NODE_NAME_REGEX),
            "min_length": DEFAULT_NAME_MIN_LENGTH,
            "max_length": DEFAULT_NAME_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "namespace",
            "kind": "Text",
            "description": "Generic Namespace, Namespaces are used to organize models into logical groups and to prevent name collisions.",
            "regex": str(NAMESPACE_REGEX),
            "min_length": DEFAULT_KIND_MIN_LENGTH,
            "max_length": DEFAULT_KIND_MAX_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "label",
            "kind": "Text",
            "description": "Human friendly representation of the name/kind",
            "optional": True,
            "max_length": 32,
            "extra": {"update": None},
        },
        {
            "name": "branch",
            "kind": "Text",
            "description": "Type of branch support for the model.",
            "enum": BranchSupportType.available_types(),
            "default_value": BranchSupportType.AWARE.value,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "default_filter",
            "kind": "Text",
            "description": "Default filter used to search for a node in addition to its ID.",
            "regex": str(NAME_REGEX),
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "order_by",
            "kind": "List",
            "description": "List of attributes to use to order the results by default",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "display_labels",
            "kind": "List",
            "description": "List of attributes to use to generate the display label",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "include_in_menu",
            "kind": "Boolean",
            "description": "Defines if objects of this kind should be included in the menu.",
            "default_value": True,
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "menu_placement",
            "kind": "Text",
            "description": "Defines where in the menu this object should be placed.",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "icon",
            "kind": "Text",
            "description": "Defines the icon to use in the menu. Must be a valid value from the MDI library https://icon-sets.iconify.design/mdi/",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "description",
            "kind": "Text",
            "optional": True,
            "description": "Short description of the Generic.",
            "max_length": DEFAULT_DESCRIPTION_LENGTH,
            "extra": {"update": None},
        },
        {
            "name": "hierarchical",
            "kind": "Boolean",
            "description": "Defines if the Generic support the hierarchical mode.",
            "optional": True,
            "default_value": False,
            "extra": {"update": None},
        },
        {
            "name": "used_by",
            "kind": "List",
            "description": "List of Nodes that are referencing this Generic",
            "optional": True,
            "extra": {"update": None},
        },
        {
            "name": "uniqueness_constraints",
            "kind": "List",
            "description": "List of multi-element uniqueness constraints that can combine relationships and attributes",
            "optional": True,
            "extra": {"update": None},
        },
    ],
    "relationships": [
        {
            "name": "attributes",
            "peer": "SchemaAttribute",
            "identifier": "schema__node__attributes",
            "cardinality": "many",
            "branch": BranchSupportType.AWARE.value,
            "optional": True,
        },
        {
            "name": "relationships",
            "peer": "SchemaRelationship",
            "identifier": "schema__node__relationships",
            "cardinality": "many",
            "branch": BranchSupportType.AWARE.value,
            "optional": True,
        },
    ],
}

internal = InternalSchema(
    version=None,
    nodes=[
        node_schema,
        attribute_schema,
        relationship_schema,
        generic_schema,
    ],
)
