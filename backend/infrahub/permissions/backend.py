from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.constants import AssignedPermissions


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(self, db: InfrahubDatabase, account_id: str, branch: Branch) -> AssignedPermissions: ...

    @abstractmethod
    async def has_permission(self, db: InfrahubDatabase, account_id: str, permission: str, branch: Branch) -> bool: ...
