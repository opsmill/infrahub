from unittest.mock import AsyncMock, patch

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.tasks import refresh_diff_all
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.workflows.catalogue import DIFF_REFRESH


class TestRefreshDiffAll:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def test_refresh_diff_all_only_refreshes_current_branch_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
    ) -> None:
        """When a branch is created, diffed, deleted, and recreated with the same name multiple times,
        refresh_diff_all should only refresh the diff for the current incarnation of the branch,
        not stale diffs from previous deleted incarnations."""

        branch_name = "branch-reuse"

        # --- First incarnation: create branch, make change, generate diff, delete branch ---
        branch1 = await create_branch(db=db, branch_name=branch_name)
        p1 = await Node.init(schema="TestPerson", branch=branch1, db=db)
        await p1.new(name="Alice", height=165, db=db)
        await p1.save(db=db)

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch1)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch1)

        await branch1.delete(db=db)
        del registry.branch[branch_name]
        registry.schema.purge_inactive_branches(active_branches=[default_branch.name])

        # --- Second incarnation: create branch with same name, make change, generate diff, delete branch ---
        branch2 = await create_branch(db=db, branch_name=branch_name)
        p2 = await Node.init(schema="TestPerson", branch=branch2, db=db)
        await p2.new(name="Bob", height=180, db=db)
        await p2.save(db=db)

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)

        await branch2.delete(db=db)
        del registry.branch[branch_name]
        registry.schema.purge_inactive_branches(active_branches=[default_branch.name])

        # --- Third incarnation: create branch with same name, make change, generate diff ---
        branch3 = await create_branch(db=db, branch_name=branch_name)
        p3 = await Node.init(schema="TestPerson", branch=branch3, db=db)
        await p3.new(name="Charlie", height=175, db=db)
        await p3.save(db=db)

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch3)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch3)

        # Call refresh_diff_all with mocked workflow submission and database access
        mock_workflow = AsyncMock()
        context = InfrahubContext(
            branch=BranchContext(name=branch_name),
            account=AccountSession(authenticated=True, account_id="test", auth_type=AuthType.NONE),
        )

        with (
            patch("infrahub.core.diff.tasks.get_database", return_value=db),
            patch("infrahub.core.diff.tasks.get_workflow", return_value=mock_workflow),
            patch("infrahub.core.diff.tasks.add_tags", new_callable=AsyncMock),
        ):
            await refresh_diff_all.fn(branch_name=branch_name, context=context)

        # Count how many DIFF_REFRESH submissions were made
        submit_calls = mock_workflow.submit_workflow.call_args_list
        diff_refresh_calls = [call for call in submit_calls if call.kwargs.get("workflow") == DIFF_REFRESH]

        # refresh_diff_all should only submit 1 refresh for the current branch's diff.
        # The bug: it finds DiffRoot nodes from all 3 incarnations and submits 3 refreshes.
        assert len(diff_refresh_calls) == 1, (
            f"Expected 1 diff refresh for the current branch, "
            f"but got {len(diff_refresh_calls)}. "
            f"refresh_diff_all is refreshing stale diffs from deleted branch incarnations. "
            f"Submitted diff IDs: {[call.kwargs['parameters']['diff_id'] for call in diff_refresh_calls]}"
        )
