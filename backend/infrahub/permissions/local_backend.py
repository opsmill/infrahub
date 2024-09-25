from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import GlobalPermission, ObjectPermission, fetch_permissions
from infrahub.core.constants import PermissionDecision

from .backend import PermissionBackend

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.constants import AssignedPermissions


class LocalPermissionBackend(PermissionBackend):
    wildcard_values = ["any", "*"]

    def compute_specificity(self, permission: ObjectPermission) -> int:
        specificity = 0
        if permission.branch not in self.wildcard_values:
            specificity += 1
        if permission.namespace not in self.wildcard_values:
            specificity += 1
        if permission.name not in self.wildcard_values:
            specificity += 1
        if permission.action not in self.wildcard_values:
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
                and permission.action in [action, *self.wildcard_values]
            ):
                # Compute the specifity of a permission to keep the decision of the most specific if two or more permissions overlap
                specificity = self.compute_specificity(permission=permission)
                if specificity > highest_specificity:
                    most_specific_permission = permission.decision
                    highest_specificity = specificity
                elif specificity == highest_specificity and permission.decision == PermissionDecision.DENY.value:
                    most_specific_permission = permission.decision

        return most_specific_permission == PermissionDecision.ALLOW.value

    async def load_permissions(self, db: InfrahubDatabase, account_id: str, branch: Branch) -> AssignedPermissions:
        return await fetch_permissions(db=db, account_id=account_id, branch=branch)

    async def has_permission(self, db: InfrahubDatabase, account_id: str, permission: str, branch: Branch) -> bool:
        granted_permissions = await self.load_permissions(db=db, account_id=account_id, branch=branch)
        global_permissions: list[GlobalPermission] = granted_permissions["global_permissions"]
        object_permissions: list[ObjectPermission] = granted_permissions["object_permissions"]

        if permission.startswith("global:"):
            return permission in [str(p) for p in global_permissions]

        return self.resolve_object_permission(permissions=object_permissions, permission_to_check=permission)
