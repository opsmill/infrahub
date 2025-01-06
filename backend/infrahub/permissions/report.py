from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.permissions.manager import PermissionManager
    from infrahub.permissions.types import KindPermissions


__all__ = ["report_schema_permissions"]


def get_permission_report(  # noqa: PLR0911
    permission_manager: PermissionManager,
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
    decision = permission_manager.report_object_permission(namespace=node.namespace, name=node.name, action=action)

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
    branch: Branch, permission_manager: PermissionManager, schemas: list[MainSchemaTypes]
) -> list[KindPermissions]:
    global_permission_report: dict[GlobalPermissions, bool] = {}
    for perm in GlobalPermissions:
        global_permission_report[perm] = permission_manager.resolve_global_permission(
            permission_to_check=GlobalPermission(action=perm.value, decision=PermissionDecision.ALLOW_ALL.value)
        )

    permission_objects: list[KindPermissions] = []
    for node in schemas:
        permission_objects.append(
            {
                "kind": node.kind,
                "create": get_permission_report(
                    permission_manager=permission_manager,
                    branch=branch,
                    node=node,
                    action="create",
                    global_permission_report=global_permission_report,
                ),
                "delete": get_permission_report(
                    permission_manager=permission_manager,
                    branch=branch,
                    node=node,
                    action="delete",
                    global_permission_report=global_permission_report,
                ),
                "update": get_permission_report(
                    permission_manager=permission_manager,
                    branch=branch,
                    node=node,
                    action="update",
                    global_permission_report=global_permission_report,
                ),
                "view": get_permission_report(
                    permission_manager=permission_manager,
                    branch=branch,
                    node=node,
                    action="view",
                    global_permission_report=global_permission_report,
                ),
            }
        )

    return permission_objects
