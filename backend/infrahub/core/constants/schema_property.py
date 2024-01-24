from enum import Enum


class FlagProperty(Enum):
    IS_VISIBLE = "is_visible"
    IS_PROTECTED = "is_protected"


class NodeProperty(Enum):
    SOURCE = "source"
    OWNER = "owner"
