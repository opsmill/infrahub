from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.types import AssignedPermissions, get_global_permission_for_kind

if TYPE_CHECKING:
    from infrahub.core.account import ObjectPermission
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes

__all__ = ["PermissionResolver"]


class PermissionResolver:
    """Stateless permission decision engine.

    Given loaded permissions, resolves any permission query without
    touching the database or requiring an account session.
    """

    wildcard_values = ["*"]
    wildcard_actions = ["any"]

    def __init__(self, permissions: AssignedPermissions) -> None:
        self.permissions = permissions
        self._global_report: dict[GlobalPermissions, bool] | None = None

    def _compute_specificity(self, permission: ObjectPermission) -> int:
        """Return how specific a permission is.

        More-specific permissions take priority when multiple rules match.
        """
        specificity = 0
        if permission.namespace not in self.wildcard_values:
            specificity += 1
        if permission.name not in self.wildcard_values:
            specificity += 1
        if permission.action not in self.wildcard_actions:
            specificity += 1
        if not permission.decision & PermissionDecisionFlag.ALLOW_ALL:
            specificity += 1
        return specificity

    def is_super_admin(self) -> bool:
        return self.resolve_global_permission(action=GlobalPermissions.SUPER_ADMIN.value)

    def resolve_global_permission(self, action: str) -> bool:
        """Tell if a global permission is granted, given the action string."""
        grant_permission = False

        for permission in self.permissions["global_permissions"]:
            if permission.action == action:
                # Deny preempts allow
                if permission.decision == PermissionDecisionFlag.DENY:
                    return False
                grant_permission = True

        return grant_permission

    def build_global_report(self) -> dict[GlobalPermissions, bool]:
        """Precompute (and cache) the result of every global permission check."""
        if self._global_report is None:
            self._global_report = {
                perm: self.resolve_global_permission(action=perm.value) for perm in GlobalPermissions
            }
        return self._global_report

    def report_object_permission(self, namespace: str, name: str, action: str) -> PermissionDecisionFlag:
        """Given loaded permissions, return the permission decision for a kind + action."""
        highest_specificity: int = -1
        combined_decision = PermissionDecisionFlag.DENY

        for permission in self.permissions["object_permissions"]:
            if (
                permission.namespace in [namespace, *self.wildcard_values]
                and permission.name in [name, *self.wildcard_values]
                and permission.action in [action, *self.wildcard_actions]
            ):
                permission_decision = PermissionDecisionFlag(value=permission.decision)
                specificity = self._compute_specificity(permission=permission)
                if specificity > highest_specificity:
                    combined_decision = permission_decision
                    highest_specificity = specificity
                elif specificity == highest_specificity and permission_decision != PermissionDecisionFlag.DENY:
                    combined_decision |= permission_decision

        return combined_decision

    def resolve_object_permission(self, permission_to_check: ObjectPermission) -> bool:
        """Compute the permissions and check if the one provided is granted."""
        required_decision = PermissionDecisionFlag(value=permission_to_check.decision)
        combined_decision = self.report_object_permission(
            namespace=permission_to_check.namespace,
            name=permission_to_check.name,
            action=permission_to_check.action,
        )
        return combined_decision & required_decision == required_decision

    def has_permission(self, permission: GlobalPermission | ObjectPermission) -> bool:
        """Tell if a permission is granted; super admin bypasses all checks."""
        is_super = self.is_super_admin()

        if isinstance(permission, GlobalPermission):
            return self.resolve_global_permission(action=permission.action) or is_super

        return self.resolve_object_permission(permission_to_check=permission) or is_super

    def has_permissions(self, permissions: Sequence[GlobalPermission | ObjectPermission]) -> bool:
        """Return ``True`` only if *all* permissions are granted."""
        return all(self.has_permission(permission=permission) for permission in permissions)

    def get_branch_decision(  # noqa: PLR0911
        self, branch: Branch, node_schema: MainSchemaTypes, action: str
    ) -> BranchRelativePermissionDecision:
        """Compute the branch-relative permission decision for a kind/action."""
        global_report = self.build_global_report()

        if branch.status in (BranchStatus.MERGED, BranchStatus.NEED_REBASE) and action != "view":
            return BranchRelativePermissionDecision.DENY

        if global_report[GlobalPermissions.SUPER_ADMIN]:
            return BranchRelativePermissionDecision.ALLOW

        # Kind-specific global permissions for mutations
        if action != "view":
            required_global = get_global_permission_for_kind(schema=node_schema)
            if required_global is not None:
                return (
                    BranchRelativePermissionDecision.ALLOW
                    if global_report[required_global]
                    else BranchRelativePermissionDecision.DENY
                )

        # Object permissions with branch-relative logic
        is_default_branch = branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
        decision = self.report_object_permission(namespace=node_schema.namespace, name=node_schema.name, action=action)

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
