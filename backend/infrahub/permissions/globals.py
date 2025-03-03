from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.core.registry import registry


def define_global_permission_from_branch(permission: GlobalPermissions, branch_name: str) -> GlobalPermission:
    if branch_name in (GLOBAL_BRANCH_NAME, registry.default_branch):
        decision = PermissionDecision.ALLOW_DEFAULT
    else:
        decision = PermissionDecision.ALLOW_OTHER

    return GlobalPermission(
        action=permission.value,
        decision=decision.value,
    )
