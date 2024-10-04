from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.permissions.backend import PermissionBackend
    from infrahub.permissions.constants import AssignedPermissions


class PermissionManager:
    def __init__(self, backends: list[PermissionBackend]) -> None:
        self.backends = backends

    async def load_permissions(self, account_session: AccountSession) -> AssignedPermissions:
        permissions: AssignedPermissions = {"global_permissions": [], "object_permissions": []}

        for permission_backend in self.backends:
            backend_permissions = await permission_backend.load_permissions(account_id=account_session.account_id)
            permissions["global_permissions"].extend(backend_permissions["global_permissions"])
            permissions["object_permissions"].extend(backend_permissions["object_permissions"])

        return permissions

    async def has_permission(self, account_session: AccountSession, permission: str) -> bool:
        for permission_backend in self.backends:
            if permission_backend.has_permission(account_id=account_session.account_id, permission=permission):
                return True

        return False
