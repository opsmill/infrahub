from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.events.clients import AssertingPassthroughEventsClient
from prefect.events.worker import EventsWorker

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
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
    from collections.abc import AsyncGenerator, Coroutine

    from infrahub_sdk import InfrahubClient
    from prefect.client.schemas.objects import State

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


PYTHON_AUTOMATION_PREFIXES = tuple(
    f"{trigger_type.value}{NAME_SEPARATOR}"
    for trigger_type in (TriggerType.COMPUTED_ATTR_PYTHON, TriggerType.COMPUTED_ATTR_PYTHON_QUERY)
)
TASK_RUN_RESOURCE_PREFIX = "prefect.task-run."


async def count_task_runs(worker: EventsWorker, flow_run: Coroutine[Any, Any, State[Any]]) -> int:
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
