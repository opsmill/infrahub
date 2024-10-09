from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import fetch_permissions
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.registry import registry
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
    permissions = await fetch_permissions(account_id=account_session.account_id, db=db, branch=branch)
    perm_backend = LocalPermissionBackend()

    # Check for super admin permission and handle default branch edition if account is not super admin
    is_super_admin = perm_backend.resolve_global_permission(
        permissions=permissions["global_permissions"],
        permission_to_check=f"global:{GlobalPermissions.SUPER_ADMIN.value}:allow",
    )
    restrict_changes = False
    if branch.name == registry.default_branch:
        restrict_changes = not perm_backend.resolve_global_permission(
            permissions=permissions["global_permissions"],
            permission_to_check=f"global:{GlobalPermissions.EDIT_DEFAULT_BRANCH.value}:allow",
        )

    permission_objects: list[KindPermissions] = []
    for node in schemas:
        permission_base = f"object:{branch.name}:{node.namespace}:{node.name}"

        has_create = perm_backend.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:create:allow"
        )
        has_delete = perm_backend.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:delete:allow"
        )
        has_update = perm_backend.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:update:allow"
        )
        has_view = perm_backend.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:view:allow"
        )

        permission_objects.append(
            {
                "kind": node.kind,
                "create": PermissionDecision.ALLOW
                if is_super_admin or (has_create and not restrict_changes)
                else PermissionDecision.DENY,
                "delete": PermissionDecision.ALLOW
                if is_super_admin or (has_delete and not restrict_changes)
                else PermissionDecision.DENY,
                "update": PermissionDecision.ALLOW
                if is_super_admin or (has_update and not restrict_changes)
                else PermissionDecision.DENY,
                "view": PermissionDecision.ALLOW if is_super_admin or has_view else PermissionDecision.DENY,
            }
        )

    return permission_objects
