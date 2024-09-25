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

    restrict_changes = False
    if branch.name == registry.default_branch:
        restrict_changes = True
        for global_permission in permissions["global_permissions"]:
            if global_permission.action == GlobalPermissions.EDIT_DEFAULT_BRANCH.value:
                restrict_changes = False

    checker = LocalPermissionBackend()

    permission_objects: list[KindPermissions] = []

    for node in schemas:
        permission_base = f"object:{branch.name}:{node.namespace}:{node.name}"

        has_create = checker.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:create:allow"
        )
        has_delete = checker.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:delete:allow"
        )
        has_update = checker.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:update:allow"
        )
        has_view = checker.resolve_object_permission(
            permissions=permissions["object_permissions"], permission_to_check=f"{permission_base}:view:allow"
        )

        permission_objects.append(
            {
                "kind": node.kind,
                "create": PermissionDecision.ALLOW if has_create and not restrict_changes else PermissionDecision.DENY,
                "delete": PermissionDecision.ALLOW if has_delete and not restrict_changes else PermissionDecision.DENY,
                "update": PermissionDecision.ALLOW if has_update and not restrict_changes else PermissionDecision.DENY,
                "view": PermissionDecision.ALLOW if has_view else PermissionDecision.DENY,
            }
        )

    return permission_objects
