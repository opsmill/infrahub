import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fast_depends import Provider

from infrahub import lock
from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import create_branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchNotFoundError
from infrahub.graphql.mutations.models import BranchCreateModel
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_database


class TestBranchCreateRaceCondition:
    @pytest.fixture(autouse=True)
    async def _setup_lock(self, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
        lock.initialize_lock(local_only=True)

    @pytest.fixture
    def context(self, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext.init(
            branch=default_branch,
            account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
        )

    @pytest.fixture
    def branch_model(self) -> BranchCreateModel:
        return BranchCreateModel(
            name="race-test-branch",
            sync_with_git=False,
            origin_branch="main",
        )

    async def test_concurrent_create_same_branch_only_one_succeeds(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_local: WorkflowLocalExecution,
        dependency_provider: Provider,
        context: InfrahubContext,
        branch_model: BranchCreateModel,
    ) -> None:
        """Simulate a TOCTOU race: both coroutines see 'branch not found' before either creates it.

        With the distributed lock in place, exactly one should succeed and the other should fail.
        """
        real_get_by_name = Branch.get_by_name
        barrier = asyncio.Barrier(2)
        synchronized = False

        async def interleaved_get_by_name(**kwargs):
            nonlocal synchronized
            # Classic behavior case
            if kwargs.get("name") != branch_model.name or synchronized:
                return await real_get_by_name(**kwargs)

            # Both coroutines must see "not found" before either proceeds.
            # After synchronization, all subsequent calls go to the real implementation.
            try:
                return await real_get_by_name(**kwargs)
            except BranchNotFoundError:
                await barrier.wait()
                synchronized = True
                raise

        with (
            dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
            patch("infrahub.core.branch.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.core.branch.tasks.get_event_service", new_callable=AsyncMock),
            patch("infrahub.core.branch.tasks.get_component", new_callable=AsyncMock),
            patch.object(Branch, "get_by_name", side_effect=interleaved_get_by_name),
        ):
            results = await asyncio.gather(
                create_branch(model=branch_model, context=context),
                create_branch(model=branch_model, context=context),
                return_exceptions=True,
            )

        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1, (
            f"Expected exactly 1 successful branch creation, got {len(successes)}. Results: {results}"
        )
        assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}. Results: {results}"
