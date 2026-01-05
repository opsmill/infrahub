from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccountGroup
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission
    from infrahub.database import InfrahubDatabase


async def define_permissions(
    account: Node,
    db: InfrahubDatabase,
    object_permissions: list[ObjectPermission] | None = None,
    global_permissions: list[GlobalPermission] | None = None,
) -> None:
    object_permissions = object_permissions or []
    global_permissions = global_permissions or []
    permissions = []
    for object_permission in object_permissions:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(
            db=db,
            namespace=object_permission.namespace,
            name=object_permission.name,
            action=object_permission.action,
            decision=object_permission.decision,
        )
        await obj.save(db=db)
        permissions.append(obj)

    for global_permission in global_permissions:
        obj = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await obj.new(
            db=db,
            action=global_permission.action,
            decision=global_permission.decision,
        )
        await obj.save(db=db)
        permissions.append(obj)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="chief-people-officer", permissions=permissions)
    await role.save(db=db)

    group = await Node.init(db=db, schema=CoreAccountGroup)
    await group.new(db=db, name="hr", roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": account.id})
    await group.members.save(db=db)
