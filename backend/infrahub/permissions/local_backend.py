from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.account import fetch_permissions, fetch_role_permissions
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccountRole

from .backend import PermissionBackend

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.types import AssignedPermissions

__all__ = ["LocalPermissionBackend"]


class LocalPermissionBackend(PermissionBackend):
    async def load_permissions(
        self, db: InfrahubDatabase, branch: Branch, account_session: AccountSession
    ) -> AssignedPermissions:
        if not account_session.authenticated:
            anonymous_permissions: AssignedPermissions = {"global_permissions": [], "object_permissions": []}
            if not config.SETTINGS.main.allow_anonymous_access:
                return anonymous_permissions

            role = await NodeManager.get_one_by_hfid(
                db=db, kind=CoreAccountRole, hfid=[config.SETTINGS.main.anonymous_access_role]
            )
            if role:
                anonymous_permissions = await fetch_role_permissions(db=db, role_id=role.id, branch=branch)

            return anonymous_permissions

        return await fetch_permissions(db=db, account_id=account_session.account_id, branch=branch)
