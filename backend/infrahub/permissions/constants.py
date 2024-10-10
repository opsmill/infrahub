from __future__ import annotations

from enum import IntFlag
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission


class AssignedPermissions(TypedDict):
    global_permissions: list[GlobalPermission]
    object_permissions: list[ObjectPermission]


class PermissionDecisionFlag(IntFlag):
    DENY = 1
    ALLOWED_DEFAULT = 2
    ALLOWED_OTHER = 4
    ALLOWED_ALL = ALLOWED_DEFAULT | ALLOWED_OTHER
