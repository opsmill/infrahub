from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import post_process_branch_merge
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot, NameTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.diff.tasks import refresh_diff_all
from infrahub.database import InfrahubDatabase
from infrahub.workflows.catalogue import DIFF_REFRESH, DIFF_UPDATE
from infrahub.workflows.models import WorkflowDefinition

from .factories import EnrichedRootFactory


def _make_context(branch_name: str) -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name=branch_name),
        account=AccountSession(authenticated=True, account_id="test", auth_type=AuthType.NONE),
    )


def _filter_calls(mock_workflow: MagicMock, workflow: WorkflowDefinition) -> list[call]:  # type: ignore
    return [c for c in mock_workflow.submit_workflow.call_args_list if c.kwargs.get("workflow") == workflow]


class TestRefreshDiffAll:
    @pytest.fixture(autouse=True)
    def _setup(self, default_branch: Branch) -> None:
        return

    async def _call_system_under_test(
        self, db: InfrahubDatabase, diff_roots: list[EnrichedDiffRoot], branch_name: str
    ) -> MagicMock:
        mock_workflow = MagicMock()
        mock_workflow.submit_workflow = AsyncMock()

        with (
            patch("infrahub.core.diff.tasks.get_database", new_callable=AsyncMock, return_value=db),
            patch("infrahub.core.diff.tasks.get_workflow", return_value=mock_workflow),
            patch("infrahub.core.diff.tasks.add_tags", new_callable=AsyncMock),
            patch.object(DiffRepository, "get_roots_metadata", new_callable=AsyncMock, return_value=diff_roots),
        ):
            await refresh_diff_all(branch_name=branch_name, context=_make_context(branch_name))

        return mock_workflow

    async def test_refreshes_unfrozen_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="feature",
            tracking_id=BranchTrackingId(name="feature"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [root], "feature")
        diff_refresh_calls = _filter_calls(mock_workflow, DIFF_REFRESH)
        assert len(diff_refresh_calls) == 1
        assert diff_refresh_calls[0].kwargs["parameters"]["diff_id"] == root.uuid

    async def test_skips_frozen_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="feature",
            tracking_id=BranchTrackingId(name="feature"),
            is_frozen=True,
        )
        mock_workflow = await self._call_system_under_test(db, [root], "feature")
        assert len(_filter_calls(mock_workflow, DIFF_REFRESH)) == 0

    async def test_skips_same_branch_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="main",
            tracking_id=BranchTrackingId(name="main"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [root], "main")
        assert len(_filter_calls(mock_workflow, DIFF_REFRESH)) == 0

    async def test_mixed_frozen_and_unfrozen(self, db: InfrahubDatabase) -> None:
        frozen = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="feature",
            tracking_id=BranchTrackingId(name="feature"),
            is_frozen=True,
        )
        unfrozen = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="feature2",
            tracking_id=BranchTrackingId(name="feature2"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [frozen, unfrozen], "feature")
        diff_refresh_calls = _filter_calls(mock_workflow, DIFF_REFRESH)
        assert len(diff_refresh_calls) == 1
        assert diff_refresh_calls[0].kwargs["parameters"]["diff_id"] == unfrozen.uuid


class TestPostProcessBranchMerge:
    @pytest.fixture(autouse=True)
    def _setup(self, default_branch: Branch) -> None:
        return

    async def _call_system_under_test(self, db: InfrahubDatabase, diff_roots: list[EnrichedDiffRoot]) -> MagicMock:
        mock_workflow = MagicMock()
        mock_workflow.submit_workflow = AsyncMock()

        with (
            patch("infrahub.core.branch.tasks.get_database", new_callable=AsyncMock, return_value=db),
            patch("infrahub.core.branch.tasks.get_workflow", return_value=mock_workflow),
            patch("infrahub.core.branch.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.core.branch.tasks.get_run_logger"),
            patch.object(DiffRepository, "get_roots_metadata", new_callable=AsyncMock, return_value=diff_roots),
        ):
            await post_process_branch_merge(
                source_branch="merged-branch", target_branch="main", context=_make_context("main")
            )

        return mock_workflow

    async def test_updates_unfrozen_branch_tracking_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="other",
            diff_branch_name="main",
            tracking_id=BranchTrackingId(name="main"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [root])
        diff_update_calls = _filter_calls(mock_workflow, DIFF_UPDATE)
        assert len(diff_update_calls) == 1
        assert diff_update_calls[0].kwargs["parameters"]["model"].branch_name == "main"

    async def test_skips_frozen_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="other",
            diff_branch_name="main",
            tracking_id=BranchTrackingId(name="main"),
            is_frozen=True,
        )
        mock_workflow = await self._call_system_under_test(db, [root])
        assert len(_filter_calls(mock_workflow, DIFF_UPDATE)) == 0

    async def test_skips_non_branch_tracking_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="other",
            diff_branch_name="main",
            tracking_id=NameTrackingId(name="some-name"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [root])
        assert len(_filter_calls(mock_workflow, DIFF_UPDATE)) == 0

    async def test_skips_inactive_branch_diff(self, db: InfrahubDatabase) -> None:
        root = EnrichedRootFactory.build(
            base_branch_name="main",
            diff_branch_name="deleted-branch",
            tracking_id=BranchTrackingId(name="deleted-branch"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [root])
        assert len(_filter_calls(mock_workflow, DIFF_UPDATE)) == 0

    async def test_mixed_frozen_and_unfrozen(self, db: InfrahubDatabase) -> None:
        frozen = EnrichedRootFactory.build(
            base_branch_name="other",
            diff_branch_name="main",
            tracking_id=BranchTrackingId(name="main"),
            is_frozen=True,
        )
        unfrozen = EnrichedRootFactory.build(
            base_branch_name="other",
            diff_branch_name="main",
            tracking_id=BranchTrackingId(name="main"),
            is_frozen=False,
        )
        mock_workflow = await self._call_system_under_test(db, [frozen, unfrozen])
        diff_update_calls = _filter_calls(mock_workflow, DIFF_UPDATE)
        assert len(diff_update_calls) == 1
