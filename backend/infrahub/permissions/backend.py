from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.types import AssignedPermissions


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(
        self, db: InfrahubDatabase, branch: Branch, account_session: AccountSession
    ) -> AssignedPermissions: ...
