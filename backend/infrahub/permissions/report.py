from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import GlobalPermissions
from infrahub.core.registry import registry
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.types import KindPermissions


async def report_schema_permissions(
    db: InfrahubDatabase, schemas: list[MainSchemaTypes], account_session: AccountSession, branch: Branch
) -> list[KindPermissions]:
    perm_backend = LocalPermissionBackend()
    permissions = await perm_backend.load_permissions(db=db, account_id=account_session.account_id, branch=branch)

    # Check for super admin permission and handle default branch edition if account is not super admin
    is_super_admin = perm_backend.resolve_global_permission(
        permissions=permissions["global_permissions"],
        permission_to_check=f"global:{GlobalPermissions.SUPER_ADMIN.value}:allow",
    )
    restrict_changes = False
    if branch.name == registry.default_branch and not is_super_admin:
        restrict_changes = not perm_backend.resolve_global_permission(
            permissions=permissions["global_permissions"],
            permission_to_check=f"global:{GlobalPermissions.EDIT_DEFAULT_BRANCH.value}:allow",
        )

    decisions_map: dict[bool, PermissionDecisionFlag] = {
        True: PermissionDecisionFlag.ALLOWED_ALL,
        False: PermissionDecisionFlag.DENY,
    }
    decision = (
        PermissionDecisionFlag.ALLOWED_DEFAULT
        if branch.name == registry.default_branch
        else PermissionDecisionFlag.ALLOWED_OTHER
    )

    permission_objects: list[KindPermissions] = []
    for node in schemas:
        permission_base = f"object:{node.namespace}:{node.name}"

        has_create = (
            is_super_admin
            or perm_backend.resolve_object_permission(
                permissions=permissions["object_permissions"],
                permission_to_check=f"{permission_base}:create:{decision}",
            )
            and not restrict_changes
        )
        has_delete = (
            is_super_admin
            or perm_backend.resolve_object_permission(
                permissions=permissions["object_permissions"],
                permission_to_check=f"{permission_base}:delete:{decision}",
            )
            and not restrict_changes
        )
        has_update = (
            is_super_admin
            or perm_backend.resolve_object_permission(
                permissions=permissions["object_permissions"],
                permission_to_check=f"{permission_base}:update:{decision}",
            )
            and not restrict_changes
        )
        has_view = is_super_admin or perm_backend.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:view:{decision}"
        )

        permission_objects.append(
            {
                "kind": node.kind,
                "create": decisions_map[has_create],
                "delete": decisions_map[has_delete],
                "update": decisions_map[has_update],
                "view": decisions_map[has_view],
            }
        )

    return permission_objects
