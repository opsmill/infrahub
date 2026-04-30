from __future__ import annotations

from typing import TYPE_CHECKING, Self, Sequence

from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.exceptions import PermissionDeniedError
from infrahub.permissions.constants import GLOBAL_PERMISSION_DENIAL_MESSAGE, PermissionDecisionFlag
from infrahub.permissions.loader import PermissionLoader
from infrahub.permissions.resolver import PermissionResolver

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.account import ObjectPermission
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

__all__ = ["PermissionManager"]


class PermissionManager:
    def __init__(self, account_session: AccountSession, resolver: PermissionResolver) -> None:
        self.account_session = account_session
        self.resolver = resolver

    @classmethod
    async def load_for_account(cls, db: InfrahubDatabase, branch: Branch, account_session: AccountSession) -> Self:
        loader = PermissionLoader(account_session=account_session)
        permissions = await loader.load(db=db, branch=branch)
        resolver = PermissionResolver(permissions=permissions, default_branch_name=registry.default_branch)
        return cls(account_session=account_session, resolver=resolver)

    def is_super_admin(self) -> bool:
        return self.resolver.is_super_admin()

    def report_object_permission(self, namespace: str, name: str, action: str) -> PermissionDecisionFlag:
        """Given a set of permissions, return the permission decision for a given kind and action."""
        return self.resolver.report_object_permission(namespace=namespace, name=name, action=action)

    def resolve_object_permission(self, permission_to_check: ObjectPermission) -> bool:
        """Compute the permissions and check if the one provided is granted."""
        return self.resolver.resolve_object_permission(permission_to_check=permission_to_check)

    def resolve_global_permission(self, permission_to_check: GlobalPermission) -> bool:
        """Tell if a global permission is granted."""
        return self.resolver.resolve_global_permission(action=permission_to_check.action)

    def has_permission(self, permission: GlobalPermission | ObjectPermission) -> bool:
        """Tell if a permission is granted given the permissions loaded in memory."""
        return self.resolver.has_permission(permission=permission)

    def has_permissions(self, permissions: Sequence[GlobalPermission | ObjectPermission]) -> bool:
        """Same as `has_permission` but for multiple permissions, return `True` only if all permissions are granted."""
        return self.resolver.has_permissions(permissions=permissions)

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
