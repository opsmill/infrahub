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
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.graphql.mutations.models import BranchCreateModel
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_database


class TestBranchCreateRaceCondition:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

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
        """Two concurrent create_branch calls with the same name must result in exactly one branch.

        The second call should raise a ValidationError. This test simulates the TOCTOU race
        condition: both coroutines pass the existence check (Branch.get_by_name raises
        BranchNotFoundError for both) before either creates the branch.

        To force the interleaving, we patch Branch.get_by_name so it always raises
        BranchNotFoundError on the first two calls (simulating what happens when both
        concurrent checks happen before any branch is persisted), and we introduce an
        asyncio.Event-based synchronization to ensure both coroutines have passed the
        check before either proceeds to the save path.
        """
        mock_event_service = AsyncMock()
        mock_event_service.send = AsyncMock()
        mock_component = AsyncMock()
        mock_component.refresh_schema_hash = AsyncMock()

        real_get_by_name = Branch.get_by_name

        # Synchronization: both coroutines must pass the existence check before either proceeds
        check_passed_count = 0
        both_passed = asyncio.Event()

        async def interleaved_get_by_name(**kwargs):
            """Ensure both coroutines see 'branch not found' before either proceeds."""
            nonlocal check_passed_count

            if kwargs.get("name") == branch_model.name:
                # Try the real check first
                try:
                    await real_get_by_name(**kwargs)
                    # Branch already exists — if a proper lock were in place, the second
                    # caller would find it here. Raise normally.
                    raise ValidationError(f"The branch {kwargs['name']} already exists")
                except BranchNotFoundError:
                    pass

                # Branch not found — signal that this coroutine passed the check
                check_passed_count += 1
                if check_passed_count >= 2:
                    both_passed.set()
                else:
                    # Wait for the other coroutine to also pass the check
                    await both_passed.wait()

                # Now raise BranchNotFoundError as the original code expects
                raise BranchNotFoundError(identifier=kwargs["name"])

            return await real_get_by_name(**kwargs)

        with (
            dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
            patch("infrahub.core.branch.tasks.add_tags", new_callable=AsyncMock),
            patch(
                "infrahub.core.branch.tasks.get_event_service", new_callable=AsyncMock, return_value=mock_event_service
            ),
            patch("infrahub.core.branch.tasks.get_component", new_callable=AsyncMock, return_value=mock_component),
            patch.object(Branch, "get_by_name", side_effect=interleaved_get_by_name),
        ):
            results = await asyncio.gather(
                create_branch(model=branch_model, context=context),
                create_branch(model=branch_model, context=context),
                return_exceptions=True,
            )

        # Exactly one should succeed and one should fail with a ValidationError or
        # database-level constraint error
        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1, (
            f"Expected exactly 1 successful branch creation, got {len(successes)}. "
            f"Both concurrent calls succeeded, proving the race condition exists. "
            f"Results: {results}"
        )
        assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}. Results: {results}"
