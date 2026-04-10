import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import BranchCreator
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql.mutations.models import BranchCreateModel
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.services.component import InfrahubComponent


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
        context: InfrahubContext,
        branch_model: BranchCreateModel,
    ) -> None:
        """Two concurrent branch creations with the same name: exactly one should succeed."""
        component = AsyncMock(spec=InfrahubComponent)
        event_service = AsyncMock(spec=InfrahubEventService)
        workflow = AsyncMock(spec=InfrahubWorkflow)

        async def run_creator() -> None:
            async with db.start_session() as session:
                creator = BranchCreator(
                    db=session,
                    lock_registry=lock.registry,
                    component=component,
                    event_service=event_service,
                    workflow=workflow,
                )
                await creator.create(model=branch_model, context=context)

        results = await asyncio.gather(
            run_creator(),
            run_creator(),
            return_exceptions=True,
        )

        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, ValidationError)]

        assert len(successes) == 1, (
            f"Expected exactly 1 successful branch creation, got {len(successes)}. Results: {results}"
        )
        assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}. Results: {results}"
        assert "already exists" in str(failures[0])
        component.refresh_schema_hash.assert_awaited_once_with(branches=[branch_model.name])
        event_service.send.assert_awaited_once()
