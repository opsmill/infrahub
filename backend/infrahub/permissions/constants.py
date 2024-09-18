from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission


class AssignedPermissions(TypedDict):
    global_permissions: list[GlobalPermission]
    object_permissions: list[ObjectPermission]
