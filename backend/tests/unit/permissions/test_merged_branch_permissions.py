from unittest.mock import MagicMock, patch

import pytest

from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GlobalPermissions
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.resolver import PermissionResolver


@pytest.fixture
def empty_resolver() -> PermissionResolver:
    return PermissionResolver(permissions={"global_permissions": [], "object_permissions": []})


@pytest.fixture
def node() -> GenericSchema:
    return GenericSchema(namespace="Testing", name="TestNode")


@pytest.fixture
def global_report() -> dict[GlobalPermissions, bool]:
    return dict.fromkeys(GlobalPermissions, False)


@pytest.fixture
def super_admin_report() -> dict[GlobalPermissions, bool]:
    return {perm: perm == GlobalPermissions.SUPER_ADMIN for perm in GlobalPermissions}


class TestMergedBranchPermissions:
    @pytest.fixture
    def branch(self) -> Branch:
        return Branch(name="test-branch", status=BranchStatus.MERGED)

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_mutations_denied(
        self, empty_resolver: PermissionResolver, branch: Branch, node: GenericSchema, global_report: dict, action: str
    ) -> None:
        result = empty_resolver.get_branch_decision(
            branch=branch, node=node, action=action, global_report=global_report
        )
        assert result == BranchRelativePermissionDecision.DENY

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_super_admin_doesnt_bypass(
        self,
        empty_resolver: PermissionResolver,
        branch: Branch,
        node: GenericSchema,
        super_admin_report: dict,
        action: str,
    ) -> None:
        result = empty_resolver.get_branch_decision(
            branch=branch, node=node, action=action, global_report=super_admin_report
        )
        assert result == BranchRelativePermissionDecision.DENY

    @patch("infrahub.permissions.resolver.registry")
    def test_view_allowed(
        self, mock_registry: MagicMock, branch: Branch, node: GenericSchema, global_report: dict
    ) -> None:
        mock_registry.default_branch = "main"
        resolver = PermissionResolver(
            permissions={
                "global_permissions": [],
                "object_permissions": [
                    ObjectPermission(
                        namespace="Testing",
                        name="TestNode",
                        action="view",
                        decision=PermissionDecisionFlag.ALLOW_ALL.value,
                    )
                ],
            }
        )
        result = resolver.get_branch_decision(branch=branch, node=node, action="view", global_report=global_report)
        assert result == BranchRelativePermissionDecision.ALLOW


class TestNeedRebaseBranchPermissions:
    @pytest.fixture
    def branch(self) -> Branch:
        return Branch(name="test-branch", status=BranchStatus.NEED_REBASE)

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_mutations_denied(
        self, empty_resolver: PermissionResolver, branch: Branch, node: GenericSchema, global_report: dict, action: str
    ) -> None:
        result = empty_resolver.get_branch_decision(
            branch=branch, node=node, action=action, global_report=global_report
        )
        assert result == BranchRelativePermissionDecision.DENY

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_super_admin_doesnt_bypass(
        self,
        empty_resolver: PermissionResolver,
        branch: Branch,
        node: GenericSchema,
        super_admin_report: dict,
        action: str,
    ) -> None:
        result = empty_resolver.get_branch_decision(
            branch=branch, node=node, action=action, global_report=super_admin_report
        )
        assert result == BranchRelativePermissionDecision.DENY

    @patch("infrahub.permissions.resolver.registry")
    def test_view_allowed(
        self, mock_registry: MagicMock, branch: Branch, node: GenericSchema, global_report: dict
    ) -> None:
        mock_registry.default_branch = "main"
        resolver = PermissionResolver(
            permissions={
                "global_permissions": [],
                "object_permissions": [
                    ObjectPermission(
                        namespace="Testing",
                        name="TestNode",
                        action="view",
                        decision=PermissionDecisionFlag.ALLOW_ALL.value,
                    )
                ],
            }
        )
        result = resolver.get_branch_decision(branch=branch, node=node, action="view", global_report=global_report)
        assert result == BranchRelativePermissionDecision.ALLOW
