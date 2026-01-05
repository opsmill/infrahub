from __future__ import annotations

from enum import Enum


class DatabaseEdgeType(Enum):
    IS_PART_OF = "IS_PART_OF"
    HAS_ATTRIBUTE = "HAS_ATTRIBUTE"
    IS_RELATED = "IS_RELATED"
    HAS_VALUE = "HAS_VALUE"
    IS_VISIBLE = "IS_VISIBLE"
    IS_PROTECTED = "IS_PROTECTED"
    HAS_OWNER = "HAS_OWNER"
    HAS_SOURCE = "HAS_SOURCE"
    IS_RESERVED = "IS_RESERVED"
