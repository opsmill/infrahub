from abc import ABC, abstractmethod

from infrahub.core.account import GlobalPermission
from infrahub.database import InfrahubDatabase


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(self, db: InfrahubDatabase, account_id: str) -> dict[str, list[GlobalPermission]]: ...

    @abstractmethod
    async def has_permission(self, db: InfrahubDatabase, account_id: str, permission: str) -> bool: ...
