from infrahub.core.account import fetch_permissions
from infrahub.database import InfrahubDatabase

from .backends import PermissionBackend


class LocalPermissionBackend(PermissionBackend):
    async def load_permissions(self, db: InfrahubDatabase, account_id: str) -> dict[str, list[str]]:
        all_permissions = await fetch_permissions(db=db, account_id=account_id)

        return {
            "global_permissions": [str(p) for p in all_permissions.get("global_permissions", [])],
            "object_permissions": [str(p) for p in all_permissions.get("object_permissions", [])],
        }
