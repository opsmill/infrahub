from unittest.mock import MagicMock, patch

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GlobalPermissions
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from infrahub.permissions.report import get_permission_report


def _create_mock_branch(status: BranchStatus, name: str = "test-branch") -> MagicMock:
    mock_branch = MagicMock()
    mock_branch.status = status
    mock_branch.name = name
    return mock_branch


def _create_mock_node(kind: str = "TestingNode") -> MagicMock:
    mock_node = MagicMock()
    mock_node.kind = kind
    mock_node.namespace = "Testing"
    mock_node.name = "TestNode"
    mock_node.inherit_from = []
    return mock_node


def _create_global_permission_report(super_admin: bool = False) -> dict[GlobalPermissions, bool]:
    return {perm: super_admin if perm == GlobalPermissions.SUPER_ADMIN else False for perm in GlobalPermissions}


class TestMergedBranchPermissions:
    def test_permission_denies_create_on_merged_branch(self) -> None:
        """Test that create permission is DENY on merged branch."""
        mock_branch = _create_mock_branch(BranchStatus.MERGED)
        mock_node = _create_mock_node()
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=mock_branch,
            node=mock_node,
            action="create",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        # Should not have called the permission manager since it returns early
        mock_manager.report_object_permission.assert_not_called()

    def test_permission_denies_update_on_merged_branch(self) -> None:
        """Test that update permission is DENY on merged branch."""
        mock_branch = _create_mock_branch(BranchStatus.MERGED)
        mock_node = _create_mock_node()
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=mock_branch,
            node=mock_node,
            action="update",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_permission_denies_delete_on_merged_branch(self) -> None:
        """Test that delete permission is DENY on merged branch."""
        mock_branch = _create_mock_branch(BranchStatus.MERGED)
        mock_node = _create_mock_node()
        mock_manager = MagicMock()

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=mock_branch,
            node=mock_node,
            action="delete",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.DENY
        mock_manager.report_object_permission.assert_not_called()

    def test_super_admin_bypasses_merged_check(self) -> None:
        """Test that super admin can still perform actions on merged branches."""
        mock_branch = _create_mock_branch(BranchStatus.MERGED)
        mock_node = _create_mock_node()
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
        mock_branch = _create_mock_branch(BranchStatus.MERGED)
        mock_node = _create_mock_node()
        mock_manager = MagicMock()
        mock_manager.report_object_permission.return_value = PermissionDecisionFlag.ALLOW_ALL

        result = get_permission_report(
            permission_manager=mock_manager,
            branch=mock_branch,
            node=mock_node,
            action="view",
            global_permission_report=_create_global_permission_report(),
        )
        assert result == BranchRelativePermissionDecision.ALLOW
        mock_manager.report_object_permission.assert_called_once()
