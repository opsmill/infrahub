from unittest.mock import AsyncMock, patch

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import post_process_branch_merge
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.tasks import refresh_diff_all
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.workflows.catalogue import DIFF_REFRESH, DIFF_UPDATE


class TestLatestBranchTrackingDiffOnly:
    """Tests that diff refresh/update workflows only target the latest branch-tracking diff
    when a branch name has been reused across multiple create/delete cycles."""

    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _create_branch_with_diff(
        self, db: InfrahubDatabase, default_branch: Branch, branch_name: str, person_name: str
    ) -> Branch:
        branch = await create_branch(db=db, branch_name=branch_name)
        person = await Node.init(schema="TestPerson", branch=branch, db=db)
        await person.new(name=person_name, height=170, db=db)
        await person.save(db=db)
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        return branch

    async def _delete_branch(self, db: InfrahubDatabase, branch: Branch, default_branch: Branch) -> None:
        await branch.delete(db=db)
        del registry.branch[branch.name]
        registry.schema.purge_inactive_branches(active_branches=[default_branch.name])

    def _make_context(self, branch_name: str) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=branch_name),
            account=AccountSession(authenticated=True, account_id="test", auth_type=AuthType.NONE),
        )

    async def _setup_reused_branch(self, db: InfrahubDatabase, default_branch: Branch, branch_name: str) -> Branch:
        """Create a branch, diff it, delete it — twice — then create a third incarnation with a diff."""
        branch1 = await self._create_branch_with_diff(db, default_branch, branch_name, "Alice")
        await self._delete_branch(db, branch1, default_branch)

        branch2 = await self._create_branch_with_diff(db, default_branch, branch_name, "Bob")
        await self._delete_branch(db, branch2, default_branch)

        return await self._create_branch_with_diff(db, default_branch, branch_name, "Charlie")

    async def test_refresh_diff_all_only_refreshes_latest_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
    ) -> None:
        branch_name = "branch-reuse-refresh"
        await self._setup_reused_branch(db, default_branch, branch_name)

        mock_workflow = AsyncMock()
        context = self._make_context(branch_name)

        with (
            patch("infrahub.core.diff.tasks.get_database", return_value=db),
            patch("infrahub.core.diff.tasks.get_workflow", return_value=mock_workflow),
            patch("infrahub.core.diff.tasks.add_tags", new_callable=AsyncMock),
        ):
            await refresh_diff_all.fn(branch_name=branch_name, context=context)

        submit_calls = mock_workflow.submit_workflow.call_args_list
        diff_refresh_calls = [call for call in submit_calls if call.kwargs.get("workflow") == DIFF_REFRESH]

        assert len(diff_refresh_calls) == 1, (
            f"Expected 1 diff refresh, got {len(diff_refresh_calls)}. "
            f"Submitted diff IDs: {[call.kwargs['parameters']['diff_id'] for call in diff_refresh_calls]}"
        )

    async def test_post_process_branch_merge_only_updates_latest_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
    ) -> None:
        branch_name = "branch-reuse-merge"
        await self._setup_reused_branch(db, default_branch, branch_name)

        mock_workflow = AsyncMock()
        context = self._make_context(branch_name)

        with (
            patch("infrahub.core.branch.tasks.get_database", return_value=db),
            patch("infrahub.core.branch.tasks.get_workflow", return_value=mock_workflow),
            patch("infrahub.core.branch.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.core.branch.tasks.get_run_logger"),
        ):
            await post_process_branch_merge.fn(
                source_branch="some-merged-branch", target_branch=default_branch.name, context=context
            )

        submit_calls = mock_workflow.submit_workflow.call_args_list
        diff_update_calls = [call for call in submit_calls if call.kwargs.get("workflow") == DIFF_UPDATE]

        assert len(diff_update_calls) == 1, (
            f"Expected 1 diff update, got {len(diff_update_calls)}. "
            f"Submitted branch names: {[call.kwargs['parameters']['model'].branch_name for call in diff_update_calls]}"
        )
