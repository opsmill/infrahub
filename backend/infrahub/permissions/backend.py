from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.permissions.constants import AssignedPermissions


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(self, account_id: str) -> AssignedPermissions: ...

    @abstractmethod
    async def has_permission(self, account_id: str, permission: str) -> bool: ...
