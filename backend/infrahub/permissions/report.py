from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.permissions.constants import AssignedPermissions, BranchAwarePermissionDecision, PermissionDecisionFlag
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
    branch: Branch,
    node: MainSchemaTypes,
    action: str,
    is_super_admin: bool = False,
    can_edit_default_branch: bool = False,  # pylint: disable=unused-argument
) -> BranchAwarePermissionDecision:
    is_default_branch = branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)

    if is_super_admin:
        return BranchAwarePermissionDecision.ALLOW

    decision = backend.report_object_permission(
        permissions=permissions["object_permissions"], namespace=node.namespace, name=node.name, action=action
    )

    # What do we do if edit default branch global permission is set?
    # if can_edit_default_branch:
    #     decision |= PermissionDecisionFlag.ALLOW_DEFAULT

    if (
        decision == PermissionDecisionFlag.ALLOW_ALL
        or (decision & PermissionDecisionFlag.ALLOW_DEFAULT and is_default_branch)
        or (decision & PermissionDecisionFlag.ALLOW_OTHER and not is_default_branch)
    ):
        return BranchAwarePermissionDecision.ALLOW
    if decision & PermissionDecisionFlag.ALLOW_DEFAULT:
        return BranchAwarePermissionDecision.ALLOW_DEFAULT
    if decision & PermissionDecisionFlag.ALLOW_OTHER:
        return BranchAwarePermissionDecision.ALLOW_OTHER

    return BranchAwarePermissionDecision.DENY


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
    can_edit_default_branch = perm_backend.resolve_global_permission(
        permissions=permissions["global_permissions"],
        permission_to_check=GlobalPermission(
            id="",
            name="",
            action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
    )

    permission_objects: list[KindPermissions] = []
    for node in schemas:
        permission_objects.append(
            {
                "kind": node.kind,
                "create": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="create",
                    is_super_admin=is_super_admin,
                    can_edit_default_branch=can_edit_default_branch,
                ),
                "delete": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="delete",
                    is_super_admin=is_super_admin,
                    can_edit_default_branch=can_edit_default_branch,
                ),
                "update": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="update",
                    is_super_admin=is_super_admin,
                    can_edit_default_branch=can_edit_default_branch,
                ),
                "view": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="view",
                    is_super_admin=is_super_admin,
                    can_edit_default_branch=can_edit_default_branch,
                ),
            }
        )

    return permission_objects
