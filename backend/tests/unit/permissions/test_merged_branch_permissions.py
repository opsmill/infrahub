import pytest

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.resolver import PermissionResolver


@pytest.fixture
def empty_resolver() -> PermissionResolver:
    return PermissionResolver(
        permissions={"global_permissions": [], "object_permissions": []}, default_branch_name="main"
    )


@pytest.fixture
def super_admin_resolver() -> PermissionResolver:
    return PermissionResolver(
        permissions={
            "global_permissions": [
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ],
            "object_permissions": [],
        },
        default_branch_name="main",
    )


@pytest.fixture
def node_schema() -> GenericSchema:
    return GenericSchema(namespace="Testing", name="TestNode")


class TestMergedBranchPermissions:
    @pytest.fixture
    def branch(self) -> Branch:
        return Branch(name="test-branch", status=BranchStatus.MERGED)

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_mutations_denied(
        self, empty_resolver: PermissionResolver, branch: Branch, node_schema: GenericSchema, action: str
    ) -> None:
        result = empty_resolver.get_branch_decision(branch=branch, node_schema=node_schema, action=action)
        assert result == BranchRelativePermissionDecision.DENY

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_super_admin_doesnt_bypass(
        self, super_admin_resolver: PermissionResolver, branch: Branch, node_schema: GenericSchema, action: str
    ) -> None:
        result = super_admin_resolver.get_branch_decision(branch=branch, node_schema=node_schema, action=action)
        assert result == BranchRelativePermissionDecision.DENY

    def test_view_allowed(self, branch: Branch, node_schema: GenericSchema) -> None:
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
            },
            default_branch_name="main",
        )
        result = resolver.get_branch_decision(branch=branch, node_schema=node_schema, action="view")
        assert result == BranchRelativePermissionDecision.ALLOW


class TestNeedRebaseBranchPermissions:
    @pytest.fixture
    def branch(self) -> Branch:
        return Branch(name="test-branch", status=BranchStatus.NEED_REBASE)

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_mutations_denied(
        self, empty_resolver: PermissionResolver, branch: Branch, node_schema: GenericSchema, action: str
    ) -> None:
        result = empty_resolver.get_branch_decision(branch=branch, node_schema=node_schema, action=action)
        assert result == BranchRelativePermissionDecision.DENY

    @pytest.mark.parametrize("action", ["create", "update", "delete"])
    def test_super_admin_doesnt_bypass(
        self, super_admin_resolver: PermissionResolver, branch: Branch, node_schema: GenericSchema, action: str
    ) -> None:
        result = super_admin_resolver.get_branch_decision(branch=branch, node_schema=node_schema, action=action)
        assert result == BranchRelativePermissionDecision.DENY

    def test_view_allowed(self, branch: Branch, node_schema: GenericSchema) -> None:
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
            },
            default_branch_name="main",
        )
        result = resolver.get_branch_decision(branch=branch, node_schema=node_schema, action="view")
        assert result == BranchRelativePermissionDecision.ALLOW
