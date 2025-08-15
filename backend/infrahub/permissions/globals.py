from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreGlobalPermission
from infrahub.core.registry import registry

from .constants import GLOBAL_PERMISSION_DESCRIPTION

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def define_global_permission_from_branch(permission: GlobalPermissions, branch_name: str) -> GlobalPermission:
    if branch_name in (GLOBAL_BRANCH_NAME, registry.default_branch):
        decision = PermissionDecision.ALLOW_DEFAULT
    else:
        decision = PermissionDecision.ALLOW_OTHER

    return GlobalPermission(action=permission.value, decision=decision.value)


async def get_or_create_global_permission(db: InfrahubDatabase, permission: GlobalPermissions) -> CoreGlobalPermission:
    permissions = await NodeManager.query(
        db=db, schema=CoreGlobalPermission, filters={"action__value": permission.value}, limit=1
    )

    if permissions:
        return permissions[0]

    p = await Node.init(db=db, schema=CoreGlobalPermission)
    await p.new(
        db=db,
        action=permission.value,
        decision=PermissionDecision.ALLOW_ALL.value,
        description=GLOBAL_PERMISSION_DESCRIPTION[permission],
    )
    await p.save(db=db)

    return p
