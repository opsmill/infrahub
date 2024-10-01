from __future__ import annotations

from .attribute import (
    AnyAttributeType,
    AttributeInterface,
    BaseAttribute,
    BoolAttributeType,
    CheckboxAttributeType,
    DropdownFields,
    DropdownType,
    IntAttributeType,
    IPHostType,
    IPNetworkType,
    JSONAttributeType,
    ListAttributeType,
    MacAddressType,
    NumberAttributeType,
    RelatedIPAddressNodeInput,
    RelatedNodeInput,
    RelatedPrefixNodeInput,
    StrAttributeType,
    TextAttributeType,
)
from .branch import BranchType
from .interface import InfrahubInterface
from .node import InfrahubObject
from .permission import PaginatedObjectPermission
from .relationship import RelationshipNode
from .standard_node import InfrahubObjectType
from .task import TaskNodes
from .task_log import TaskLog, TaskLogEdge, TaskLogNodes

__all__ = [
    "AnyAttributeType",
    "AttributeInterface",
    "BaseAttribute",
    "BoolAttributeType",
    "BranchType",
    "CheckboxAttributeType",
    "DropdownFields",
    "DropdownType",
    "IPHostType",
    "IPNetworkType",
    "InfrahubInterface",
    "InfrahubObject",
    "InfrahubObjectType",
    "IntAttributeType",
    "JSONAttributeType",
    "ListAttributeType",
    "MacAddressType",
    "NumberAttributeType",
    "PaginatedObjectPermission",
    "RelatedIPAddressNodeInput",
    "RelatedNodeInput",
    "RelatedPrefixNodeInput",
    "RelationshipNode",
    "StrAttributeType",
    "TaskLog",
    "TaskLogEdge",
    "TaskLogNodes",
    "TaskNodes",
    "TextAttributeType",
]


RELATIONS_PROPERTY_MAP: dict[str, str] = {
    "is_visible": "_relation__is_visible",
    "is_protected": "_relation__is_protected",
    "owner": "_relation__owner",
    "source": "_relation__source",
    "updated_at": "_relation__updated_at",
    "__typename": "__typename",
}

RELATIONS_PROPERTY_MAP_REVERSED = {value: key for key, value in RELATIONS_PROPERTY_MAP.items()}
