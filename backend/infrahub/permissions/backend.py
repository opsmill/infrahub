from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.constants import AssignedPermissions, PermissionDecisionFlag


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(self, db: InfrahubDatabase, account_id: str, branch: Branch) -> AssignedPermissions: ...

    @abstractmethod
    def report_object_permission(
        self, permissions: list[ObjectPermission], namespace: str, name: str, action: str
    ) -> PermissionDecisionFlag: ...

    @abstractmethod
    async def has_permission(
        self, db: InfrahubDatabase, account_id: str, permission: GlobalPermission | ObjectPermission, branch: Branch
    ) -> bool: ...
