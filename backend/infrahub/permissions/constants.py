from __future__ import annotations

from enum import IntFlag, StrEnum, auto


class PermissionDecisionFlag(IntFlag):
    DENY = 1
    ALLOW_DEFAULT = 2
    ALLOW_OTHER = 4
    ALLOW_ALL = ALLOW_DEFAULT | ALLOW_OTHER


class BranchRelativePermissionDecision(StrEnum):
    """This enum is only used to communicate a permission decision relative to a branch."""

    DENY = auto()
    ALLOW = auto()
    ALLOW_DEFAULT = auto()
    ALLOW_OTHER = auto()
