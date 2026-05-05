from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.types import AssignedPermissions

__all__ = ["PermissionLoader"]


class PermissionLoader:
    """Loads permissions for an account session by orchestrating registered backends."""

    def __init__(self, account_session: AccountSession) -> None:
        self.account_session = account_session

    async def load(self, db: InfrahubDatabase, branch: Branch) -> AssignedPermissions:
        permissions: AssignedPermissions = {"global_permissions": [], "object_permissions": []}
        for permission_backend in registry.permission_backends:
            backend_permissions = await permission_backend.load_permissions(
                db=db, branch=branch, account_session=self.account_session
            )
            permissions["global_permissions"].extend(backend_permissions["global_permissions"])
            permissions["object_permissions"].extend(backend_permissions["object_permissions"])
        return permissions
