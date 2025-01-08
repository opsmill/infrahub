from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission
    from infrahub.permissions.constants import BranchRelativePermissionDecision


class AssignedPermissions(TypedDict):
    global_permissions: list[GlobalPermission]
    object_permissions: list[ObjectPermission]


class KindPermissions(TypedDict):
    kind: str
    create: BranchRelativePermissionDecision
    delete: BranchRelativePermissionDecision
    update: BranchRelativePermissionDecision
    view: BranchRelativePermissionDecision
