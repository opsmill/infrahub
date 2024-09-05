from infrahub.core.account import GlobalPermission, fetch_permissions
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase

from .backend import PermissionBackend


class LocalPermissionBackend(PermissionBackend):
    async def load_permissions(
        self, db: InfrahubDatabase, account_id: str, branch: Branch | str | None = None
    ) -> dict[str, list[GlobalPermission]]:
        all_permissions = await fetch_permissions(db=db, account_id=account_id, branch=branch)
        return {"global_permissions": all_permissions.get("global_permissions", [])}

    async def has_permission(
        self, db: InfrahubDatabase, account_id: str, permission: str, branch: Branch | str | None = None
    ) -> bool:
        granted_permissions = await self.load_permissions(db=db, account_id=account_id, branch=branch)
        return permission.startswith("global:") and permission in [
            str(p) for p in granted_permissions["global_permissions"]
        ]
