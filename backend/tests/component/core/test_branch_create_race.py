import asyncio
from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.components import ComponentType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.creator import BranchCreator
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql.mutations.models import BranchCreateModel
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.services.component import InfrahubComponent
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder


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
        component = create_autospec(spec=InfrahubComponent, spec_set=True)
        event_service = create_autospec(spec=InfrahubEventService, spec_set=True)
        workflow = create_autospec(spec=InfrahubWorkflow, spec_set=True)

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

    async def test_create_completes_while_the_process_holds_the_global_graph_lock(
        self,
        db: InfrahubDatabase,
        context: InfrahubContext,
        branch_model: BranchCreateModel,
    ) -> None:
        """A branch is created while another coroutine of the same process holds the graph lock for a merge."""
        graph_lock_held = asyncio.Event()
        release_graph_lock = asyncio.Event()

        async def merge() -> None:
            async with lock.registry.global_graph_lock():
                graph_lock_held.set()
                await release_graph_lock.wait()

        merge_task = asyncio.create_task(merge())
        await asyncio.wait_for(graph_lock_held.wait(), timeout=30)
        try:
            creator = BranchCreator(
                db=db,
                lock_registry=lock.registry,
                component=InfrahubComponent(
                    cache=MemoryCache(), db=db, message_bus=BusRecorder(), component_type=ComponentType.GIT_AGENT
                ),
                event_service=MemoryInfrahubEvent(),
                workflow=WorkflowRecorder(),
            )
            await asyncio.wait_for(creator.create(model=branch_model, context=context), timeout=30)

            assert not merge_task.done()
        finally:
            release_graph_lock.set()
            await merge_task

        created = await Branch.get_by_name(db=db, name=branch_model.name)
        assert created.origin_branch == branch_model.origin_branch
