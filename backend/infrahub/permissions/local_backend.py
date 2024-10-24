from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.account import GlobalPermission, ObjectPermission, fetch_permissions, fetch_role_permissions
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccountRole
from infrahub.permissions.constants import PermissionDecisionFlag

from .backend import PermissionBackend

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.constants import AssignedPermissions


class LocalPermissionBackend(PermissionBackend):
    wildcard_values = ["*"]
    wildcard_actions = ["any"]

    def _compute_specificity(self, permission: ObjectPermission) -> int:
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

    def report_object_permission(
        self, permissions: list[ObjectPermission], namespace: str, name: str, action: str
    ) -> PermissionDecisionFlag:
        """Given a set of permissions, return the permission decision for a given kind and action."""
        highest_specificity: int = -1
        combined_decision = PermissionDecisionFlag.DENY

        for permission in permissions:
            if (
                permission.namespace in [namespace, *self.wildcard_values]
                and permission.name in [name, *self.wildcard_values]
                and permission.action in [action, *self.wildcard_actions]
            ):
                permission_decision = PermissionDecisionFlag(value=permission.decision)
                # Compute the specifity of a permission to keep the decision of the most specific if two or more permissions overlap
                specificity = self._compute_specificity(permission=permission)
                if specificity > highest_specificity:
                    combined_decision = permission_decision
                    highest_specificity = specificity
                elif specificity == highest_specificity and permission_decision != PermissionDecisionFlag.DENY:
                    combined_decision |= permission_decision

        return combined_decision

    def resolve_object_permission(
        self, permissions: list[ObjectPermission], permission_to_check: ObjectPermission
    ) -> bool:
        """Compute the permissions and check if the one provided is allowed."""
        required_decision = PermissionDecisionFlag(value=permission_to_check.decision)
        combined_decision = self.report_object_permission(
            permissions=permissions,
            namespace=permission_to_check.namespace,
            name=permission_to_check.name,
            action=permission_to_check.action,
        )

        return combined_decision & required_decision == required_decision

    def resolve_global_permission(
        self, permissions: list[GlobalPermission], permission_to_check: GlobalPermission
    ) -> bool:
        grant_permission = False

        for permission in permissions:
            if permission.action == permission_to_check.action:
                # Early exit on deny as deny preempt allow
                if permission.decision == PermissionDecisionFlag.DENY:
                    return False
                grant_permission = True

        return grant_permission

    async def load_permissions(
        self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch
    ) -> AssignedPermissions:
        if not account_session.authenticated:
            anonymous_permissions: AssignedPermissions = {"global_permissions": [], "object_permissions": []}
            if not config.SETTINGS.main.allow_anonymous_access:
                return anonymous_permissions

            role = await NodeManager.get_one_by_hfid(
                db=db, kind=CoreAccountRole, hfid=[config.SETTINGS.main.anonymous_access_role]
            )
            if role:
                anonymous_permissions = await fetch_role_permissions(db=db, role_id=role.id, branch=branch)

            return anonymous_permissions

        return await fetch_permissions(db=db, account_id=account_session.account_id, branch=branch)

    async def has_permission(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        permission: GlobalPermission | ObjectPermission,
        branch: Branch,
    ) -> bool:
        granted_permissions = await self.load_permissions(db=db, account_session=account_session, branch=branch)
        is_super_admin = self.resolve_global_permission(
            permissions=granted_permissions["global_permissions"],
            permission_to_check=GlobalPermission(
                id="", name="", action=GlobalPermissions.SUPER_ADMIN, decision=PermissionDecision.ALLOW_ALL
            ),
        )

        if isinstance(permission, GlobalPermission):
            return (
                self.resolve_global_permission(
                    permissions=granted_permissions["global_permissions"], permission_to_check=permission
                )
                or is_super_admin
            )

        return (
            self.resolve_object_permission(
                permissions=granted_permissions["object_permissions"], permission_to_check=permission
            )
            or is_super_admin
        )
