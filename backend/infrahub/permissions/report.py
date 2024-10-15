from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.permissions.constants import AssignedPermissions, PermissionDecisionFlag
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.backend import PermissionBackend
    from infrahub.permissions.types import KindPermissions


def get_permission_report(
    backend: PermissionBackend,
    permissions: AssignedPermissions,
    node: MainSchemaTypes,
    action: str,
    is_super_admin: bool = False,
) -> PermissionDecisionFlag:
    return (
        PermissionDecisionFlag.ALLOW_ALL
        if is_super_admin
        else backend.report_object_permission(
            permissions=permissions["object_permissions"],
            namespace=node.namespace,
            name=node.name,
            action=action,
        )
    )


async def report_schema_permissions(
    db: InfrahubDatabase, schemas: list[MainSchemaTypes], account_session: AccountSession, branch: Branch
) -> list[KindPermissions]:
    perm_backend = LocalPermissionBackend()
    permissions = await perm_backend.load_permissions(db=db, account_id=account_session.account_id, branch=branch)

    is_super_admin = perm_backend.resolve_global_permission(
        permissions=permissions["global_permissions"],
        permission_to_check=GlobalPermission(
            id="", name="", action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
        ),
    )

    permission_objects: list[KindPermissions] = []
    for node in schemas:
        permission_report: KindPermissions = {
            "kind": node.kind,
            "create": get_permission_report(
                backend=perm_backend, permissions=permissions, node=node, action="create", is_super_admin=is_super_admin
            ),
            "delete": get_permission_report(
                backend=perm_backend, permissions=permissions, node=node, action="delete", is_super_admin=is_super_admin
            ),
            "update": get_permission_report(
                backend=perm_backend, permissions=permissions, node=node, action="update", is_super_admin=is_super_admin
            ),
            "view": get_permission_report(
                backend=perm_backend, permissions=permissions, node=node, action="view", is_super_admin=is_super_admin
            ),
        }

        # What do we do if edit default branch global permission is set?
        # if not restrict_changes:
        #     for key in permission_report:
        #         permission_report[key] |= PermissionDecisionFlag.ALLOW_DEFAULT

        permission_objects.append(permission_report)

    return permission_objects
