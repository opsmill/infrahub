from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.events.clients import AssertingPassthroughEventsClient
from prefect.events.schemas.automations import EventTrigger
from prefect.events.schemas.events import ResourceSpecification
from prefect.events.worker import EventsWorker

from infrahub import config
from infrahub.computed_attribute.tasks import computed_attribute_setup_python, process_transform_lifecycle
from infrahub.core import registry
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository
from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import (
    CAR_PERSON_PYTHON_SCHEMA,
    ScopedRecomputeTestBase,
    create_transform01,
)
from tests.helpers.agnostic_edges import TEST_ACTOR_ID
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from infrahub_sdk import InfrahubClient
    from prefect.client.schemas.objects import State

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services import InfrahubServices


PYTHON_AUTOMATION_PREFIXES = tuple(
    f"{trigger_type.value}{NAME_SEPARATOR}"
    for trigger_type in (TriggerType.COMPUTED_ATTR_PYTHON, TriggerType.COMPUTED_ATTR_PYTHON_QUERY)
)
TASK_RUN_RESOURCE_PREFIX = "prefect.task-run."
EXTRA_BRANCHES_FEW = 2
EXTRA_BRANCHES_MANY = 10


async def count_task_runs(worker: EventsWorker, flow_run: Awaitable[State[Any]]) -> int:
    """Run a flow called with ``return_state=True`` and count the distinct task runs its events report."""
    state = await flow_run
    flow_run_resource = f"prefect.flow-run.{state.state_details.flow_run_id}"
    await asyncio.to_thread(worker.wait_until_empty)

    client = worker._client
    assert isinstance(client, AssertingPassthroughEventsClient)
    return len(
        {
            event.resource.id
            for event in client.events
            if event.resource.id.startswith(TASK_RUN_RESOURCE_PREFIX)
            and any(related.id == flow_run_resource for related in event.related)
        }
    )


async def create_open_branch(db: InfrahubDatabase, name: str) -> Branch:
    return await create_branch(branch_name=name, db=db)


async def delete_branch(db: InfrahubDatabase, branch: Branch) -> None:
    # The registry keeps a deleted branch until it is purged, and the gather reads its branch list from there.
    await BranchDataDeleter(db=db, batch_size=config.SETTINGS.database.query_size_limit).delete(
        branch=branch, user_id=TEST_ACTOR_ID
    )
    await registry.purge_inactive_branches(db=db)


def extra_branch_names() -> set[str]:
    return {
        branch.name
        for branch in registry.branch.values()
        if not branch.is_global and branch.name != registry.default_branch
    }


async def open_extra_branches(db: InfrahubDatabase, count: int) -> None:
    index = 0
    while len(extra_branch_names()) < count:
        name = f"open-{index}"
        if name not in extra_branch_names():
            await create_open_branch(db=db, name=name)
        index += 1
    assert len(extra_branch_names()) == count


@dataclass
class ReconcileRun:
    db: InfrahubDatabase
    worker: EventsWorker
    context: EventContext
    label: str
    transform_id: str


@dataclass
class ReconcileCountCase:
    name: str
    count_task_runs: Callable[[ReconcileRun], Awaitable[int]]


async def count_branch_deleted(run: ReconcileRun) -> int:
    branch = await create_open_branch(db=run.db, name=f"deleted-{run.label}")
    await delete_branch(db=run.db, branch=branch)
    return await count_task_runs(
        worker=run.worker,
        flow_run=computed_attribute_setup_python(
            context=run.context,
            branch_name=branch.name,
            event_name=BranchDeletedEvent.event_name,
            return_state=True,
        ),
    )


async def count_schema_updated(run: ReconcileRun) -> int:
    return await count_task_runs(
        worker=run.worker,
        flow_run=computed_attribute_setup_python(
            context=run.context,
            branch_name=registry.default_branch,
            event_name=SchemaUpdatedEvent.event_name,
            return_state=True,
        ),
    )


def count_transform_lifecycle(action: MutationAction) -> Callable[[ReconcileRun], Awaitable[int]]:
    async def count(run: ReconcileRun) -> int:
        return await count_task_runs(
            worker=run.worker,
            flow_run=process_transform_lifecycle(
                branch_name=registry.default_branch,
                transform_id=run.transform_id,
                action=action.value,
                context=run.context,
                return_state=True,
            ),
        )

    return count


RECONCILE_COUNT_CASES = [
    ReconcileCountCase(name="branch_deleted", count_task_runs=count_branch_deleted),
    ReconcileCountCase(name="schema_updated", count_task_runs=count_schema_updated),
    ReconcileCountCase(name="transform_created", count_task_runs=count_transform_lifecycle(MutationAction.CREATED)),
    ReconcileCountCase(name="transform_updated", count_task_runs=count_transform_lifecycle(MutationAction.UPDATED)),
    ReconcileCountCase(name="transform_deleted", count_task_runs=count_transform_lifecycle(MutationAction.DELETED)),
]


async def count_every_case(run: ReconcileRun, extra_branches: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in RECONCILE_COUNT_CASES:
        await open_extra_branches(db=run.db, count=extra_branches)
        counts[case.name] = await case.count_task_runs(run)
        assert len(extra_branch_names()) == extra_branches
    return counts


class TestReconcileTaskRuns(ScopedRecomputeTestBase):
    WORKFLOW = TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES

    @pytest.fixture(scope="class")
    async def transform_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> dict[str, str]:
        repo = await create_transform01(db=db, branch_name=default_branch.name)
        transform01 = await NodeManager.get_one_by_default_filter(
            db=db, id="transform01", kind=InfrahubKind.TRANSFORMPYTHON, raise_on_error=True
        )

        query_opaque = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query_opaque.new(
            db=db,
            name="query_opaque",
            query="query { TestCar { edges { node { display_label } } } }",
            models=["TestCar"],
        )
        await query_opaque.save(db=db)

        transform_opaque = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
        await transform_opaque.new(
            db=db,
            name="transform_opaque",
            file_path="transform.py",
            class_name="Transform",
            query=query_opaque,
            repository=repo,
        )
        await transform_opaque.save(db=db)

        await load_schema(db=db, schema=CAR_PERSON_PYTHON_SCHEMA, update_db=True)

        return {"transform01": transform01.id, "transform_opaque": transform_opaque.id}

    @pytest.fixture(scope="class")
    async def counts_with_2_branches(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        admin_account: CoreAccount,
        transform_dataset: dict[str, str],
        events_worker: EventsWorker,
    ) -> dict[str, int]:
        run = ReconcileRun(
            db=db,
            worker=events_worker,
            context=self._context(admin_account, default_branch),
            label="few",
            transform_id=transform_dataset["transform01"],
        )
        return await count_every_case(run=run, extra_branches=EXTRA_BRANCHES_FEW)

    @pytest.fixture(scope="class")
    async def counts_with_10_branches(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        admin_account: CoreAccount,
        transform_dataset: dict[str, str],
        events_worker: EventsWorker,
        counts_with_2_branches: dict[str, int],
    ) -> dict[str, int]:
        run = ReconcileRun(
            db=db,
            worker=events_worker,
            context=self._context(admin_account, default_branch),
            label="many",
            transform_id=transform_dataset["transform01"],
        )
        return await count_every_case(run=run, extra_branches=EXTRA_BRANCHES_MANY)

    @pytest.fixture(scope="class")
    async def events_worker(self, service: InfrahubServices) -> AsyncGenerator[EventsWorker, None]:
        EventsWorker.set_client_override(AssertingPassthroughEventsClient)
        worker = EventsWorker.instance()
        try:
            yield worker
        finally:
            await asyncio.to_thread(worker.drain)
            EventsWorker.set_client_override(None)

    @pytest.fixture(scope="class", autouse=True)
    async def delete_python_automations(self, service: InfrahubServices) -> AsyncGenerator[None, None]:
        yield
        async with get_prefect_client(sync_client=False) as prefect_client:
            for automation in await gather_all_automations(client=prefect_client):
                if automation.name.startswith(PYTHON_AUTOMATION_PREFIXES):
                    await prefect_client.delete_automation(automation_id=automation.id)

    @pytest.mark.parametrize("case", RECONCILE_COUNT_CASES, ids=[c.name for c in RECONCILE_COUNT_CASES])
    async def test_task_run_count_does_not_depend_on_branch_count(
        self,
        case: ReconcileCountCase,
        counts_with_2_branches: dict[str, int],
        counts_with_10_branches: dict[str, int],
    ) -> None:
        assert counts_with_2_branches[case.name] > 0
        assert counts_with_10_branches[case.name] == counts_with_2_branches[case.name]

    async def _python_automation_branch_filters(self) -> dict[str, str | list[str] | None]:
        """Map each Python computed-attribute automation name to the branch filter of its trigger."""
        async with get_prefect_client(sync_client=False) as prefect_client:
            automations = await gather_all_automations(client=prefect_client)
        filters: dict[str, str | list[str] | None] = {}
        for automation in automations:
            if not automation.name.startswith(PYTHON_AUTOMATION_PREFIXES):
                continue
            assert isinstance(automation.trigger, EventTrigger)
            match = automation.trigger.match
            assert isinstance(match, ResourceSpecification)
            filters[automation.name] = match.root.get("infrahub.branch.name")
        return filters

    async def test_branch_deletion_keeps_the_automations_a_full_reconcile_builds(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        admin_account: CoreAccount,
        transform_dataset: dict[str, str],
    ) -> None:
        branch = await create_open_branch(db=db, name="repo-commit-changed")
        repo = await NodeManager.get_one_by_default_filter(
            db=db, id="repo01", kind=CoreReadOnlyRepository, branch=branch, raise_on_error=True
        )
        repo.commit.value = "commit02"
        await repo.save(db=db)

        def automation(branch_name: str, attribute: str) -> str:
            return f"{TriggerType.COMPUTED_ATTR_PYTHON.value}{NAME_SEPARATOR}{branch_name}{NAME_SEPARATOR}TestCar_{attribute}"

        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform01"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )

        python_prefix = f"{TriggerType.COMPUTED_ATTR_PYTHON.value}{NAME_SEPARATOR}"
        filters_before = await self._python_automation_branch_filters()
        assert {name: f for name, f in filters_before.items() if name.startswith(python_prefix)} == {
            automation(default_branch.name, "computed_desc_python"): ["!repo-commit-changed"],
            automation(default_branch.name, "computed_desc_python_opaque"): ["!repo-commit-changed"],
            automation("repo-commit-changed", "computed_desc_python"): "repo-commit-changed",
            automation("repo-commit-changed", "computed_desc_python_opaque"): "repo-commit-changed",
        }

        await delete_branch(db=db, branch=branch)
        await computed_attribute_setup_python(
            context=self._context(admin_account, default_branch),
            branch_name=branch.name,
            event_name=BranchDeletedEvent.event_name,
        )

        filters_after = await self._python_automation_branch_filters()
        assert {name: f for name, f in filters_after.items() if name.startswith(python_prefix)} == {
            automation(default_branch.name, "computed_desc_python"): None,
            automation(default_branch.name, "computed_desc_python_opaque"): None,
        }
        assert [name for name in filters_after if "repo-commit-changed" in name] == []
