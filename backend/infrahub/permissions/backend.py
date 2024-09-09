from abc import ABC, abstractmethod

from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(
        self, db: InfrahubDatabase, account_id: str, branch: Branch | str | None = None
    ) -> dict[str, list[GlobalPermission]]: ...

    @abstractmethod
    async def has_permission(
        self, db: InfrahubDatabase, account_id: str, permission: str, branch: Branch | str | None = None
    ) -> bool: ...
