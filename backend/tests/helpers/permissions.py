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
    role_name: str = "chief-people-officer",
    group_name: str = "hr",
) -> None:
    """Grant an account a set of permissions through a new role and group.

    Args:
        account: Account to add to the new group.
        db: Database connection instance.
        object_permissions: Object permissions to grant.
        global_permissions: Global permissions to grant.
        role_name: Name of the role to create; both role and group names are unique, so a caller
            granting several accounts in one database must pass its own.
        group_name: Name of the group to create.

    """
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
    await role.new(db=db, name=role_name, permissions=permissions)
    await role.save(db=db)

    group = await Node.init(db=db, schema=CoreAccountGroup)
    await group.new(db=db, name=group_name, roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": account.id})
    await group.members.save(db=db)
