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
from .mixin import GetListMixin
from .node import InfrahubObject
from .relationship import RelationshipNode
from .standard_node import InfrahubObjectType
from .task import TaskNodes
from .task_log import TaskLog, TaskLogEdge, TaskLogNodes

__all__ = [
    "AttributeInterface",
    "BaseAttribute",
    "DropdownFields",
    "DropdownType",
    "IPHostType",
    "IPNetworkType",
    "MacAddressType",
    "TextAttributeType",
    "NumberAttributeType",
    "CheckboxAttributeType",
    "StrAttributeType",
    "IntAttributeType",
    "BoolAttributeType",
    "ListAttributeType",
    "JSONAttributeType",
    "AnyAttributeType",
    "BranchType",
    "InfrahubInterface",
    "GetListMixin",
    "InfrahubObject",
    "InfrahubObjectType",
    "RelatedIPAddressNodeInput",
    "RelatedNodeInput",
    "RelatedPrefixNodeInput",
    "RelationshipNode",
    "TaskLog",
    "TaskLogEdge",
    "TaskLogNodes",
    "TaskNodes",
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
