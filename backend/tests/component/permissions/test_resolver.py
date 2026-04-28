from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.registry import registry
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.resolver import PermissionResolver

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.permissions.types import AssignedPermissions


def _make_resolver(
    global_permissions: list[GlobalPermission] | None = None,
    object_permissions: list[ObjectPermission] | None = None,
) -> PermissionResolver:
    permissions: AssignedPermissions = {
        "global_permissions": global_permissions or [],
        "object_permissions": object_permissions or [],
    }
    return PermissionResolver(permissions=permissions)


@pytest.fixture
def empty_resolver() -> PermissionResolver:
    return _make_resolver()


@pytest.fixture
def node(register_core_models_schema: None) -> MainSchemaTypes:
    return registry.schema.get(name=InfrahubKind.TAG)


class TestComputeSpecificity:
    def test_all_wildcards(self, empty_resolver: PermissionResolver) -> None:
        perm = ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
        assert empty_resolver._compute_specificity(perm) == 0

    def test_specific_namespace(self, empty_resolver: PermissionResolver) -> None:
        perm = ObjectPermission(namespace="Infra", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
        assert empty_resolver._compute_specificity(perm) == 1

    def test_specific_namespace_and_name(self, empty_resolver: PermissionResolver) -> None:
        perm = ObjectPermission(
            namespace="Infra", name="Device", action="any", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert empty_resolver._compute_specificity(perm) == 2

    def test_all_specific(self, empty_resolver: PermissionResolver) -> None:
        perm = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert empty_resolver._compute_specificity(perm) == 3

    def test_deny_adds_bonus(self, empty_resolver: PermissionResolver) -> None:
        perm = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.DENY.value
        )
        assert empty_resolver._compute_specificity(perm) == 4

    def test_allow_default_no_bonus(self, empty_resolver: PermissionResolver) -> None:
        """ALLOW_DEFAULT (2) shares bits with ALLOW_ALL (6), so no bonus."""
        perm = ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value)
        assert empty_resolver._compute_specificity(perm) == 0

    def test_allow_other_no_bonus(self, empty_resolver: PermissionResolver) -> None:
        """ALLOW_OTHER (4) shares bits with ALLOW_ALL (6), so no bonus."""
        perm = ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value)
        assert empty_resolver._compute_specificity(perm) == 0

    def test_deny_with_specific_fields(self, empty_resolver: PermissionResolver) -> None:
        """DENY (1) does NOT share bits with ALLOW_ALL (6), so bonus applies."""
        perm = ObjectPermission(namespace="Infra", name="*", action="any", decision=PermissionDecision.DENY.value)
        assert empty_resolver._compute_specificity(perm) == 2


class TestResolveGlobalPermission:
    def test_no_permissions(self, empty_resolver: PermissionResolver) -> None:
        assert empty_resolver.resolve_global_permission(action=GlobalPermissions.SUPER_ADMIN.value) is False

    def test_allow(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        assert resolver.resolve_global_permission(action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value) is True

    def test_deny_preempts_allow(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
                ),
                GlobalPermission(
                    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.DENY.value
                ),
            ]
        )
        assert resolver.resolve_global_permission(action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value) is False

    def test_unrelated_action_ignored(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        assert resolver.resolve_global_permission(action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value) is False

    def test_is_super_admin(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        assert resolver.is_super_admin() is True

    def test_not_super_admin(self, empty_resolver: PermissionResolver) -> None:
        assert empty_resolver.is_super_admin() is False


class TestReportObjectPermission:
    def test_no_permissions_returns_deny(self, empty_resolver: PermissionResolver) -> None:
        assert (
            empty_resolver.report_object_permission(namespace="Infra", name="Device", action="create")
            == PermissionDecisionFlag.DENY
        )

    def test_unrelated_kind_does_not_grant(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(
                    namespace="Infra", name="Device", action="any", decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        assert (
            resolver.report_object_permission(namespace="Builtin", name="Tag", action="create")
            == PermissionDecisionFlag.DENY
        )

    def test_wildcard_allow(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
            ]
        )
        assert (
            resolver.report_object_permission(namespace="Infra", name="Device", action="create")
            == PermissionDecisionFlag.ALLOW_ALL
        )

    def test_specific_deny_overrides_wildcard_allow(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value),
                ObjectPermission(namespace="Builtin", name="Tag", action="any", decision=PermissionDecision.DENY.value),
            ]
        )
        assert (
            resolver.report_object_permission(namespace="Builtin", name="Tag", action="create")
            == PermissionDecisionFlag.DENY
        )

    def test_specific_allow_overrides_wildcard_deny(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.DENY.value),
                ObjectPermission(
                    namespace="Builtin", name="Tag", action="any", decision=PermissionDecision.ALLOW_ALL.value
                ),
            ]
        )
        assert (
            resolver.report_object_permission(namespace="Builtin", name="Tag", action="create")
            == PermissionDecisionFlag.ALLOW_ALL
        )

    def test_allow_default_only(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value)
            ]
        )
        result = resolver.report_object_permission(namespace="Infra", name="Device", action="create")
        assert result == PermissionDecisionFlag.ALLOW_DEFAULT
        assert result & PermissionDecisionFlag.ALLOW_DEFAULT
        assert not (result & PermissionDecisionFlag.ALLOW_OTHER)

    def test_allow_other_only(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value)
            ]
        )
        result = resolver.report_object_permission(namespace="Infra", name="Device", action="create")
        assert result == PermissionDecisionFlag.ALLOW_OTHER
        assert result & PermissionDecisionFlag.ALLOW_OTHER
        assert not (result & PermissionDecisionFlag.ALLOW_DEFAULT)

    def test_same_specificity_combines_allow(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(
                    namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value
                ),
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value),
            ]
        )
        result = resolver.report_object_permission(namespace="Infra", name="Device", action="create")
        assert result == PermissionDecisionFlag.ALLOW_ALL


class TestResolveObjectPermission:
    def test_allow_all_granted(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
            ]
        )
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert resolver.resolve_object_permission(permission_to_check=check) is True

    def test_allow_default_denied_when_only_allow_other(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value)
            ]
        )
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_DEFAULT.value
        )
        assert resolver.resolve_object_permission(permission_to_check=check) is False

    def test_allow_other_denied_when_only_allow_default(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value)
            ]
        )
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_OTHER.value
        )
        assert resolver.resolve_object_permission(permission_to_check=check) is False

    def test_deny_is_denied(self, empty_resolver: PermissionResolver) -> None:
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert empty_resolver.resolve_object_permission(permission_to_check=check) is False


class TestHasPermission:
    def test_object_permission_granted(self) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
            ]
        )
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert resolver.has_permission(permission=check) is True

    def test_object_permission_denied(self, empty_resolver: PermissionResolver) -> None:
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert empty_resolver.has_permission(permission=check) is False

    def test_global_permission_granted(self) -> None:
        check = GlobalPermission(
            action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value
        )
        resolver = _make_resolver(global_permissions=[check])
        assert resolver.has_permission(permission=check) is True

    def test_global_permission_denied(self, empty_resolver: PermissionResolver) -> None:
        check = GlobalPermission(
            action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value
        )
        assert empty_resolver.has_permission(permission=check) is False

    def test_super_admin_bypass_for_object(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        check = ObjectPermission(
            namespace="Infra", name="Device", action="create", decision=PermissionDecision.ALLOW_ALL.value
        )
        assert resolver.has_permission(permission=check) is True

    def test_super_admin_bypass_for_global(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        check = GlobalPermission(
            action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value
        )
        assert resolver.has_permission(permission=check) is True

    def test_has_permissions_all_required(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
                ),
                GlobalPermission(
                    action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value
                ),
            ]
        )
        checks = [
            GlobalPermission(
                action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
            ),
            GlobalPermission(action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value),
        ]
        assert resolver.has_permissions(permissions=checks) is True

    def test_has_permissions_fails_if_one_missing(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
                ),
            ]
        )
        checks = [
            GlobalPermission(
                action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
            ),
            GlobalPermission(action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value),
        ]
        assert resolver.has_permissions(permissions=checks) is False


class TestBuildGlobalReport:
    def test_empty_permissions(self, empty_resolver: PermissionResolver) -> None:
        report = empty_resolver.build_global_report()
        assert all(v is False for v in report.values())
        assert GlobalPermissions.SUPER_ADMIN in report

    def test_reflects_granted_permissions(self) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.MANAGE_SCHEMA.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        report = resolver.build_global_report()
        assert report[GlobalPermissions.MANAGE_SCHEMA] is True
        assert report[GlobalPermissions.SUPER_ADMIN] is False


class TestGetBranchDecision:
    def test_merged_branch_denies_mutations_even_super_admin(self, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        branch = Branch(name="merged-branch", status=BranchStatus.MERGED)
        assert (
            resolver.get_branch_decision(branch=branch, node=node, action="create")
            == BranchRelativePermissionDecision.DENY
        )

    def test_merged_branch_allows_view(self, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        branch = Branch(name="merged-branch", status=BranchStatus.MERGED)
        assert (
            resolver.get_branch_decision(branch=branch, node=node, action="view")
            == BranchRelativePermissionDecision.ALLOW
        )

    def test_need_rebase_denies_mutations(self, empty_resolver: PermissionResolver, node: MainSchemaTypes) -> None:
        branch = Branch(name="rebase-branch", status=BranchStatus.NEED_REBASE)
        assert (
            empty_resolver.get_branch_decision(branch=branch, node=node, action="update")
            == BranchRelativePermissionDecision.DENY
        )

    def test_super_admin_allows_on_open_branch(self, default_branch: Branch, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        assert (
            resolver.get_branch_decision(branch=default_branch, node=node, action="create")
            == BranchRelativePermissionDecision.ALLOW
        )

    def test_manage_accounts_required_and_granted(
        self, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        resolver = _make_resolver(
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.MANAGE_ACCOUNTS.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ]
        )
        node = registry.schema.get(name=InfrahubKind.ACCOUNTGROUP)
        result = resolver.get_branch_decision(branch=default_branch, node=node, action="create")
        assert result == BranchRelativePermissionDecision.ALLOW

    def test_manage_accounts_required_but_denied(
        self, register_core_models_schema: None, empty_resolver: PermissionResolver, default_branch: Branch
    ) -> None:
        node = registry.schema.get(name=InfrahubKind.ACCOUNTGROUP)
        result = empty_resolver.get_branch_decision(branch=default_branch, node=node, action="update")
        assert result == BranchRelativePermissionDecision.DENY

    def test_manage_accounts_not_required_for_view(
        self, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        """View action should skip the kind-specific global check entirely."""
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
            ]
        )
        node = registry.schema.get(name=InfrahubKind.ACCOUNTGROUP)
        result = resolver.get_branch_decision(branch=default_branch, node=node, action="view")
        assert result == BranchRelativePermissionDecision.ALLOW

    def test_allow_default_on_default_branch(self, default_branch: Branch, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value)
            ]
        )
        assert (
            resolver.get_branch_decision(branch=default_branch, node=node, action="create")
            == BranchRelativePermissionDecision.ALLOW
        )

    def test_allow_default_on_other_branch(self, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value)
            ]
        )
        branch = Branch(name="feature-123", status=BranchStatus.OPEN)
        assert (
            resolver.get_branch_decision(branch=branch, node=node, action="create")
            == BranchRelativePermissionDecision.ALLOW_DEFAULT
        )

    def test_allow_other_on_other_branch(self, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value)
            ]
        )
        branch = Branch(name="feature-123", status=BranchStatus.OPEN)
        assert (
            resolver.get_branch_decision(branch=branch, node=node, action="create")
            == BranchRelativePermissionDecision.ALLOW
        )

    def test_allow_other_on_default_branch(self, default_branch: Branch, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value)
            ]
        )
        assert (
            resolver.get_branch_decision(branch=default_branch, node=node, action="create")
            == BranchRelativePermissionDecision.ALLOW_OTHER
        )

    def test_no_permissions_deny(
        self, empty_resolver: PermissionResolver, default_branch: Branch, node: MainSchemaTypes
    ) -> None:
        assert (
            empty_resolver.get_branch_decision(branch=default_branch, node=node, action="create")
            == BranchRelativePermissionDecision.DENY
        )

    def test_allow_all_on_any_branch(self, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_ALL.value)
            ]
        )
        for branch_name in ("main", "feature-123"):
            branch = Branch(name=branch_name, status=BranchStatus.OPEN)
            assert (
                resolver.get_branch_decision(branch=branch, node=node, action="create")
                == BranchRelativePermissionDecision.ALLOW
            )

    def test_precomputed_global_report(
        self, empty_resolver: PermissionResolver, default_branch: Branch, node: MainSchemaTypes
    ) -> None:
        report: dict[GlobalPermissions, bool] = dict.fromkeys(GlobalPermissions, False)
        report[GlobalPermissions.SUPER_ADMIN] = True
        assert (
            empty_resolver.get_branch_decision(branch=default_branch, node=node, action="create", global_report=report)
            == BranchRelativePermissionDecision.ALLOW
        )

    def test_global_branch_name_treated_as_default(self, node: MainSchemaTypes) -> None:
        resolver = _make_resolver(
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_DEFAULT.value)
            ]
        )
        branch = Branch(name="-global-", status=BranchStatus.OPEN)
        assert (
            resolver.get_branch_decision(branch=branch, node=node, action="create")
            == BranchRelativePermissionDecision.ALLOW
        )
