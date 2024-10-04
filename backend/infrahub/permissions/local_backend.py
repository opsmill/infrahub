from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import GlobalPermission, ObjectPermission, fetch_permissions
from infrahub.core.constants import GlobalPermissions, PermissionDecision

from .backend import PermissionBackend

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.constants import AssignedPermissions


class LocalPermissionBackend(PermissionBackend):
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    wildcard_values = ["*"]
    wildcard_actions = ["any"]

    def compute_specificity(self, permission: ObjectPermission) -> int:
        specificity = 0
        if permission.branch not in self.wildcard_values:
            specificity += 1
        if permission.namespace not in self.wildcard_values:
            specificity += 1
        if permission.name not in self.wildcard_values:
            specificity += 1
        if permission.action not in self.wildcard_actions:
            specificity += 1
        return specificity

    def resolve_object_permission(self, permissions: list[ObjectPermission], permission_to_check: str) -> bool:
        """Compute the permissions and check if the one provided is allowed."""
        if not permission_to_check.startswith("object:"):
            return False

        most_specific_permission: str | None = None
        highest_specificity: int = -1
        _, branch, namespace, name, action, _ = permission_to_check.split(":")

        for permission in permissions:
            if (
                permission.branch in [branch, *self.wildcard_values]
                and permission.namespace in [namespace, *self.wildcard_values]
                and permission.name in [name, *self.wildcard_values]
                and permission.action in [action, *self.wildcard_actions]
            ):
                # Compute the specifity of a permission to keep the decision of the most specific if two or more permissions overlap
                specificity = self.compute_specificity(permission=permission)
                if specificity > highest_specificity:
                    most_specific_permission = permission.decision
                    highest_specificity = specificity
                elif specificity == highest_specificity and permission.decision == PermissionDecision.DENY.value:
                    most_specific_permission = permission.decision

        return most_specific_permission == PermissionDecision.ALLOW.value

    def resolve_global_permission(self, permissions: list[GlobalPermission], permission_to_check: str) -> bool:
        if not permission_to_check.startswith("global:"):
            return False

        _, action, _ = permission_to_check.split(":")
        grant_permission = False

        for permission in permissions:
            if permission.action == action:
                # Early exit on deny as deny preempt allow
                if permission.decision == PermissionDecision.DENY.value:
                    return False
                grant_permission = True

        return grant_permission

    async def load_permissions(self, account_id: str) -> AssignedPermissions:
        return await fetch_permissions(db=self.db, account_id=account_id, branch=self.branch)

    async def has_permission(self, account_id: str, permission: str) -> bool:
        granted_permissions = await self.load_permissions(account_id=account_id)

        # Check for a final super admin permission at the end if no permissions have matched before
        return (
            self.resolve_global_permission(
                permissions=granted_permissions["global_permissions"], permission_to_check=permission
            )
            or self.resolve_object_permission(
                permissions=granted_permissions["object_permissions"], permission_to_check=permission
            )
            or self.resolve_global_permission(
                permissions=granted_permissions["global_permissions"],
                permission_to_check=f"global:{GlobalPermissions.SUPER_ADMIN.value}:{PermissionDecision.ALLOW.value}",
            )
        )
