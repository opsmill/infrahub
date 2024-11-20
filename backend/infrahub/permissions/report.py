from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.permissions.constants import AssignedPermissions, BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.backend import PermissionBackend
    from infrahub.permissions.types import KindPermissions


def get_permission_report(  # noqa: PLR0911
    backend: PermissionBackend,
    permissions: AssignedPermissions,
    branch: Branch,
    node: MainSchemaTypes,
    action: str,
    global_permission_report: dict[GlobalPermissions, bool],
) -> BranchRelativePermissionDecision:
    if global_permission_report[GlobalPermissions.SUPER_ADMIN]:
        return BranchRelativePermissionDecision.ALLOW

    if action != "view":
        if node.kind in (InfrahubKind.ACCOUNTGROUP, InfrahubKind.ACCOUNTROLE, InfrahubKind.GENERICACCOUNT) or (
            isinstance(node, NodeSchema) and InfrahubKind.GENERICACCOUNT in node.inherit_from
        ):
            return (
                BranchRelativePermissionDecision.ALLOW
                if global_permission_report[GlobalPermissions.MANAGE_ACCOUNTS]
                else BranchRelativePermissionDecision.DENY
            )
        if node.kind in (InfrahubKind.BASEPERMISSION, InfrahubKind.GLOBALPERMISSION, InfrahubKind.OBJECTPERMISSION) or (
            isinstance(node, NodeSchema) and InfrahubKind.BASEPERMISSION in node.inherit_from
        ):
            return (
                BranchRelativePermissionDecision.ALLOW
                if global_permission_report[GlobalPermissions.MANAGE_PERMISSIONS]
                else BranchRelativePermissionDecision.DENY
            )
        if node.kind in (InfrahubKind.GENERICREPOSITORY, InfrahubKind.REPOSITORY, InfrahubKind.READONLYREPOSITORY) or (
            isinstance(node, NodeSchema) and InfrahubKind.GENERICREPOSITORY in node.inherit_from
        ):
            return (
                BranchRelativePermissionDecision.ALLOW
                if global_permission_report[GlobalPermissions.MANAGE_REPOSITORIES]
                else BranchRelativePermissionDecision.DENY
            )

    is_default_branch = branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
    decision = backend.report_object_permission(
        permissions=permissions["object_permissions"], namespace=node.namespace, name=node.name, action=action
    )

    if (
        decision == PermissionDecisionFlag.ALLOW_ALL
        or (decision & PermissionDecisionFlag.ALLOW_DEFAULT and is_default_branch)
        or (decision & PermissionDecisionFlag.ALLOW_OTHER and not is_default_branch)
    ):
        return BranchRelativePermissionDecision.ALLOW
    if decision & PermissionDecisionFlag.ALLOW_DEFAULT:
        return BranchRelativePermissionDecision.ALLOW_DEFAULT
    if decision & PermissionDecisionFlag.ALLOW_OTHER:
        return BranchRelativePermissionDecision.ALLOW_OTHER

    return BranchRelativePermissionDecision.DENY


async def report_schema_permissions(
    db: InfrahubDatabase, schemas: list[MainSchemaTypes], account_session: AccountSession, branch: Branch
) -> list[KindPermissions]:
    perm_backend = LocalPermissionBackend()
    permissions = await perm_backend.load_permissions(db=db, account_session=account_session, branch=branch)

    global_permission_report: dict[GlobalPermissions, bool] = {}
    for perm in GlobalPermissions:
        global_permission_report[perm] = perm_backend.resolve_global_permission(
            permissions=permissions["global_permissions"],
            permission_to_check=GlobalPermission(action=perm.value, decision=PermissionDecision.ALLOW_ALL.value),
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
                    global_permission_report=global_permission_report,
                ),
                "delete": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="delete",
                    global_permission_report=global_permission_report,
                ),
                "update": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="update",
                    global_permission_report=global_permission_report,
                ),
                "view": get_permission_report(
                    backend=perm_backend,
                    permissions=permissions,
                    branch=branch,
                    node=node,
                    action="view",
                    global_permission_report=global_permission_report,
                ),
            }
        )

    return permission_objects
