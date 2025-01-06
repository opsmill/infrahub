from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.exceptions import PermissionDeniedError
from infrahub.permissions.constants import GLOBAL_PERMISSION_DENIAL_MESSAGE, PermissionDecisionFlag

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.account import ObjectPermission
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.types import AssignedPermissions

__all__ = ["PermissionManager"]


class PermissionManager:
    wildcard_values = ["*"]
    wildcard_actions = ["any"]

    def __init__(self, account_session: AccountSession) -> None:
        self.account_session = account_session
        self.permissions: AssignedPermissions = {"global_permissions": [], "object_permissions": []}

    async def load_permissions(self, db: InfrahubDatabase, branch: Branch) -> None:
        """Load permissions from the configured backends into memory."""
        for permission_backend in registry.permission_backends:
            backend_permissions = await permission_backend.load_permissions(
                db=db, branch=branch, account_session=self.account_session
            )
            self.permissions["global_permissions"].extend(backend_permissions["global_permissions"])
            self.permissions["object_permissions"].extend(backend_permissions["object_permissions"])

    def _compute_specificity(self, permission: ObjectPermission) -> int:
        """Return how specific a permission is."""
        specificity = 0
        if permission.namespace not in self.wildcard_values:
            specificity += 1
        if permission.name not in self.wildcard_values:
            specificity += 1
        if permission.action not in self.wildcard_actions:
            specificity += 1
        if not permission.decision & PermissionDecisionFlag.ALLOW_ALL:
            specificity += 1
        return specificity

    def report_object_permission(self, namespace: str, name: str, action: str) -> PermissionDecisionFlag:
        """Given a set of permissions, return the permission decision for a given kind and action."""
        highest_specificity: int = -1
        combined_decision = PermissionDecisionFlag.DENY

        for permission in self.permissions["object_permissions"]:
            if (
                permission.namespace in [namespace, *self.wildcard_values]
                and permission.name in [name, *self.wildcard_values]
                and permission.action in [action, *self.wildcard_actions]
            ):
                permission_decision = PermissionDecisionFlag(value=permission.decision)
                # Compute the specifity of a permission to keep the decision of the most specific if two or more permissions overlap
                specificity = self._compute_specificity(permission=permission)
                if specificity > highest_specificity:
                    combined_decision = permission_decision
                    highest_specificity = specificity
                elif specificity == highest_specificity and permission_decision != PermissionDecisionFlag.DENY:
                    combined_decision |= permission_decision

        return combined_decision

    def resolve_object_permission(self, permission_to_check: ObjectPermission) -> bool:
        """Compute the permissions and check if the one provided is granted."""
        required_decision = PermissionDecisionFlag(value=permission_to_check.decision)
        combined_decision = self.report_object_permission(
            namespace=permission_to_check.namespace, name=permission_to_check.name, action=permission_to_check.action
        )

        return combined_decision & required_decision == required_decision

    def resolve_global_permission(self, permission_to_check: GlobalPermission) -> bool:
        """Tell if a global permission is granted."""
        grant_permission = False

        for permission in self.permissions["global_permissions"]:
            if permission.action == permission_to_check.action:
                # Early exit on deny as deny preempt allow
                if permission.decision == PermissionDecisionFlag.DENY:
                    return False
                grant_permission = True

        return grant_permission

    def has_permission(self, permission: GlobalPermission | ObjectPermission) -> bool:
        """Tell if a permission is granted given the permissions loaded in memory."""
        is_super_admin = self.resolve_global_permission(
            permission_to_check=GlobalPermission(
                action=GlobalPermissions.SUPER_ADMIN, decision=PermissionDecision.ALLOW_ALL
            ),
        )

        if isinstance(permission, GlobalPermission):
            return self.resolve_global_permission(permission_to_check=permission) or is_super_admin

        return self.resolve_object_permission(permission_to_check=permission) or is_super_admin

    def has_permissions(self, permissions: Sequence[GlobalPermission | ObjectPermission]) -> bool:
        """Same as `has_permission` but for multiple permissions, return `True` only if all permissions are granted."""
        return all(self.has_permission(permission=permission) for permission in permissions)

    def raise_for_permission(self, permission: GlobalPermission | ObjectPermission, message: str = "") -> None:
        """Same as `has_permission` but raise a `PermissionDeniedError` if the permission is not granted."""
        if self.has_permission(permission=permission):
            return

        if not message:
            if isinstance(permission, GlobalPermission) and permission.action in GLOBAL_PERMISSION_DENIAL_MESSAGE:
                message = GLOBAL_PERMISSION_DENIAL_MESSAGE[permission.action]
            else:
                message = f"You do not have the following permission: {permission!s}"

        raise PermissionDeniedError(message=message)

    def raise_for_permissions(
        self, permissions: Sequence[GlobalPermission | ObjectPermission], message: str = ""
    ) -> None:
        """Same as `has_permissions` but raise a `PermissionDeniedError` if any of the permissions is not granted."""
        if self.has_permissions(permissions=permissions):
            return

        if not message:
            message = f"You do not have one of the following permissions: {' | '.join([str(p) for p in permissions])}"

        raise PermissionDeniedError(message=message)
