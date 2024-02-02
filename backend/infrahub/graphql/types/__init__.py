from __future__ import annotations

from typing import Dict

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
    NumberAttributeType,
    RelatedNodeInput,
    StrAttributeType,
    TextAttributeType,
)
from .branch import BranchType
from .interface import InfrahubInterface
from .mixin import GetListMixin
from .node import InfrahubObject
from .standard_node import InfrahubObjectType
from .task import TaskNodes
from .task_log import TaskLog, TaskLogEdge, TaskLogNodes

__all__ = [
    "RelatedNodeInput",
    "AttributeInterface",
    "BaseAttribute",
    "DropdownFields",
    "DropdownType",
    "IPHostType",
    "IPNetworkType",
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
    "TaskLog",
    "TaskLogEdge",
    "TaskLogNodes",
    "TaskNodes",
]


RELATIONS_PROPERTY_MAP: Dict[str, str] = {
    "is_visible": "_relation__is_visible",
    "is_protected": "_relation__is_protected",
    "owner": "_relation__owner",
    "source": "_relation__source",
    "updated_at": "_relation__updated_at",
    "__typename": "__typename",
}

RELATIONS_PROPERTY_MAP_REVERSED = {value: key for key, value in RELATIONS_PROPERTY_MAP.items()}
