import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fast_depends import Provider

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.initialization import create_branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_database


class TestMergeTaskLock:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    @pytest.fixture
    async def source_branch(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
    ) -> Branch:
        lock.initialize_lock(local_only=True)
        return await create_branch(branch_name="branch_1", db=db)

    @pytest.fixture
    async def second_source_branch(self, db: InfrahubDatabase, source_branch: Branch) -> Branch:
        return await create_branch(branch_name="branch_2", db=db)

    @pytest.fixture
    def context(self, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext.init(
            branch=default_branch,
            account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
        )

    @staticmethod
    async def _mock_do_merge(
        db: InfrahubDatabase,
        log: Any,  # noqa: ARG004
        branch: Branch,
        context: Any,  # noqa: ARG004
        proposed_change_id: str | None = None,  # noqa: ARG004
    ) -> list:
        branch.status = BranchStatus.MERGED
        await branch.save(db=db)
        registry.branch[branch.name] = branch
        return []

    @staticmethod
    def _mock_event_service() -> AsyncMock:
        mock_svc = AsyncMock()
        mock_svc.send = AsyncMock()
        return mock_svc

    async def test_concurrent_merges_same_branch_only_execute_once(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        workflow_local: WorkflowLocalExecution,
        dependency_provider: Provider,
        context: InfrahubContext,
    ) -> None:
        """When two merges of the same branch run concurrently, _do_merge_branch is called only once."""
        mock_do_merge_fn = AsyncMock(side_effect=self._mock_do_merge)
        mock_get_event_svc = AsyncMock(return_value=self._mock_event_service())

        with (
            dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
            patch("infrahub.core.branch.tasks._do_merge_branch", mock_do_merge_fn),
            patch("infrahub.core.branch.tasks.get_event_service", mock_get_event_svc),
        ):
            await asyncio.gather(
                merge_branch(branch=source_branch.name, context=context),
                merge_branch(branch=source_branch.name, context=context),
            )

        mock_do_merge_fn.assert_awaited_once()

        merged_branch = await Branch.get_by_name(db=db, name=source_branch.name)
        assert merged_branch.status is BranchStatus.MERGED

    async def test_concurrent_merges_different_branches_both_execute_sequentially(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        second_source_branch: Branch,
        workflow_local: WorkflowLocalExecution,
        dependency_provider: Provider,
        context: InfrahubContext,
    ) -> None:
        """When two merges of different branches run concurrently, both execute but not at the same time."""
        concurrent_count = 0
        max_concurrent = 0

        async def tracking_mock_do_merge(
            db: InfrahubDatabase, log: Any, branch: Branch, context: Any, proposed_change_id: str | None = None
        ):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            branch.status = BranchStatus.MERGED
            await branch.save(db=db)
            registry.branch[branch.name] = branch
            return []

        mock_do_merge_fn = AsyncMock(side_effect=tracking_mock_do_merge)
        mock_get_event_svc = AsyncMock(return_value=self._mock_event_service())

        with (
            dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
            patch("infrahub.core.branch.tasks._do_merge_branch", mock_do_merge_fn),
            patch("infrahub.core.branch.tasks.get_event_service", mock_get_event_svc),
        ):
            await asyncio.gather(
                merge_branch(branch=source_branch.name, context=context),
                merge_branch(branch=second_source_branch.name, context=context),
            )

        assert mock_do_merge_fn.await_count == 2
        assert max_concurrent == 1

        merged_1 = await Branch.get_by_name(db=db, name=source_branch.name)
        assert merged_1.status is BranchStatus.MERGED
        merged_2 = await Branch.get_by_name(db=db, name=second_source_branch.name)
        assert merged_2.status is BranchStatus.MERGED
