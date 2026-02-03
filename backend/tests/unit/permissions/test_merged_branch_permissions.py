from unittest.mock import MagicMock, patch

from infrahub_sdk.schema.main import GenericSchema

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GlobalPermissions
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.report import get_permission_report


def _create_branch(status: BranchStatus, name: str = "test-branch") -> Branch:
    return Branch(name=name, status=status)


def _create_node(kind: str = "TestingNode") -> GenericSchema:
    return GenericSchema(kind=kind, namespace="Testing", name="TestNode", inherit_from=[])


def _create_global_permission_report(super_admin: bool = False) -> dict[GlobalPermissions, bool]:
    return {perm: super_admin if perm == GlobalPermissions.SUPER_ADMIN else False for perm in GlobalPermissions}


class TestMergedBranchPermissions:
    def test_permission_denies_create_on_merged_branch(self) -> None:
        """Test that create permission is DENY on merged branch."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.MERGED),
            node=_create_node(),
            action="create",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        # Should not have called the permission manager since it returns early
        mock_manager.report_object_permission.assert_not_called()

    def test_permission_denies_update_on_merged_branch(self) -> None:
        """Test that update permission is DENY on merged branch."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.MERGED),
            node=_create_node(),
            action="update",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_permission_denies_delete_on_merged_branch(self) -> None:
        """Test that delete permission is DENY on merged branch."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.MERGED),
            node=_create_node(),
            action="delete",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_super_admin_bypasses_merged_check(self) -> None:
        """Test that super admin can still perform actions on merged branches."""
        mock_branch = _create_branch(BranchStatus.MERGED)
        mock_node = _create_node()
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=mock_branch,
            node=mock_node,
            action="create",
            global_permission_report=_create_global_permission_report(super_admin=True),
        )
        assert result == BranchRelativePermissionDecision.ALLOW
        mock_manager.report_object_permission.assert_not_called()

    @patch("infrahub.permissions.report.registry")
    def test_permission_allows_view_on_merged_branch(self, mock_registry: MagicMock) -> None:
        """Test that view permission proceeds to normal logic on merged branch."""
        mock_registry.default_branch = "main"
        mock_manager = MagicMock()
        mock_manager.report_object_permission.return_value = PermissionDecisionFlag.ALLOW_ALL

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.MERGED),
            node=_create_node(),
            action="view",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.ALLOW
        mock_manager.report_object_permission.assert_called_once()


class TestNeedRebaseBranchPermissions:
    """Tests for permission blocking on branches needing rebase."""

    def test_permission_denies_create_on_need_rebase_branch(self) -> None:
        """Test that create permission is DENY on branch needing rebase."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.NEED_REBASE),
            node=_create_node(),
            action="create",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_permission_denies_update_on_need_rebase_branch(self) -> None:
        """Test that update permission is DENY on branch needing rebase."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.NEED_REBASE),
            node=_create_node(),
            action="update",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_permission_denies_delete_on_need_rebase_branch(self) -> None:
        """Test that delete permission is DENY on branch needing rebase."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.NEED_REBASE),
            node=_create_node(),
            action="delete",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_super_admin_bypasses_need_rebase_check(self) -> None:
        """Test that super admin can still perform actions on branches needing rebase."""
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.NEED_REBASE),
            node=_create_node(),
            action="create",
            global_permission_report=_create_global_permission_report(super_admin=True),
        )
        assert result == BranchRelativePermissionDecision.ALLOW
        mock_manager.report_object_permission.assert_not_called()

    @patch("infrahub.permissions.report.registry")
    def test_permission_allows_view_on_need_rebase_branch(self, mock_registry: MagicMock) -> None:
        """Test that view permission proceeds to normal logic on branch needing rebase."""
        mock_registry.default_branch = "main"
        mock_manager = MagicMock()
        mock_manager.report_object_permission.return_value = PermissionDecisionFlag.ALLOW_ALL

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=_create_branch(BranchStatus.NEED_REBASE),
            node=_create_node(),
            action="view",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.ALLOW
        mock_manager.report_object_permission.assert_called_once()
