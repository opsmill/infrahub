import asyncio
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterDeploymentId
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.exceptions import ObjectNotFound

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workers.infrahub_async import InfrahubWorkerAsync
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.initialization import setup_work_queues
from infrahub.workflows.models import WorkflowDefinition
from tests.helpers.test_worker import TestWorkerInfrahubAsync
from tests.integration.services.adapters.workflow.fixture_flows import (
    PRIORITY_CHILD,
    PRIORITY_GRANDCHILD,
    PRIORITY_PARENT,
    PRIORITY_PARENT_BLOCKING,
)

HTTP_REQUEST_LOG = re.compile(r'^HTTP Request: (?P<method>\w+) (?P<url>\S+) "HTTP/[\d.]+ (?P<status>\d+)')

UNKNOWN_WORKFLOW = WorkflowDefinition(
    name="dispatch_fixture_unknown",
    module=DUMMY_FLOW.module,
    function=DUMMY_FLOW.function,
)


@dataclass(frozen=True)
class DeploymentRequest:
    method: str
    path: str
    status: int


def dispatch_requests(caplog: pytest.LogCaptureFixture) -> list[DeploymentRequest]:
    """Return the deployment lookups and flow run creations sent to the task manager, in order."""
    requests = []
    for record in caplog.records:
        match = HTTP_REQUEST_LOG.match(record.getMessage()) if record.name == "httpx" else None
        if match is None:
            continue
        path = urlparse(match["url"]).path.removeprefix("/api")
        if path.startswith("/deployments/name/") or path.endswith("/create_flow_run"):
            requests.append(DeploymentRequest(method=match["method"], path=path, status=int(match["status"])))
    return requests


def lookup(workflow: WorkflowDefinition) -> DeploymentRequest:
    return DeploymentRequest(method="GET", path=f"/deployments/name/{workflow.full_name}", status=200)


def create(deployment_id: UUID, status: int = 201) -> DeploymentRequest:
    return DeploymentRequest(method="POST", path=f"/deployments/{deployment_id}/create_flow_run", status=status)


def build_context() -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name="main", id="1111aaaa-0000-0000-0000-000000000000"),
        account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="account-a"),
    )


class TestWorkflowDispatch(TestWorkerInfrahubAsync):
    @pytest.fixture(scope="class")
    async def dispatch_deployments(self, work_pool: WorkPool, prefect_client: PrefectClient) -> None:
        await setup_work_queues(client=prefect_client)
        for workflow in [DUMMY_FLOW, PRIORITY_PARENT, PRIORITY_CHILD, PRIORITY_GRANDCHILD, PRIORITY_PARENT_BLOCKING]:
            await workflow.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)

    @pytest.fixture
    def http_requests(self, caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
        caplog.set_level(logging.INFO, logger="httpx")
        return caplog

    @classmethod
    async def submit_dummy(cls, service: WorkflowWorkerExecution, priority: WorkflowPriority) -> UUID:
        workflow_info = await service.submit_workflow(
            workflow=DUMMY_FLOW, parameters={"data": DummyInput(firstname="John", lastname="Doe")}, priority=priority
        )
        return workflow_info.id

    @classmethod
    async def deployment_run_ids(cls, client: PrefectClient, workflow: WorkflowDefinition) -> set[UUID]:
        deployment = await client.read_deployment_by_name(name=workflow.full_name)
        runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(deployment_id=FlowRunFilterDeploymentId(any_=[deployment.id]))
        )
        return {run.id for run in runs}

    @classmethod
    async def wait_for_dispatched_run(
        cls, client: PrefectClient, workflow: WorkflowDefinition, seen_ids: set[UUID]
    ) -> FlowRun:
        """Poll until the single new flow run of the deployment appears since ``seen_ids`` was captured.

        Raises:
            TimeoutError: When no new flow run appears within 30 seconds.

        """
        async with asyncio.timeout(30):
            while True:
                new_ids = await cls.deployment_run_ids(client=client, workflow=workflow) - seen_ids
                if new_ids:
                    assert len(new_ids) == 1
                    return await client.read_flow_run(flow_run_id=new_ids.pop())
                await asyncio.sleep(0.5)

    async def test_repeated_dispatches_look_up_the_deployment_once(
        self,
        dispatch_deployments: None,
        prefect_client: PrefectClient,
        http_requests: pytest.LogCaptureFixture,
    ) -> None:
        deployment = await prefect_client.read_deployment_by_name(name=DUMMY_FLOW.full_name)
        http_requests.clear()
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())

        high_run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)
        low_run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.LOW)

        assert dispatch_requests(caplog=http_requests) == [
            lookup(workflow=DUMMY_FLOW),
            create(deployment_id=deployment.id),
            create(deployment_id=deployment.id),
        ]
        high_run = await prefect_client.read_flow_run(flow_run_id=high_run_id)
        low_run = await prefect_client.read_flow_run(flow_run_id=low_run_id)
        assert (high_run.deployment_id, high_run.work_queue_name, high_run.parent_task_run_id) == (
            deployment.id,
            WorkflowPriority.HIGH.queue_name,
            None,
        )
        assert (low_run.deployment_id, low_run.work_queue_name, low_run.parent_task_run_id) == (
            deployment.id,
            WorkflowPriority.LOW.queue_name,
            None,
        )

    async def test_deployment_saved_again_keeps_the_looked_up_id(
        self,
        dispatch_deployments: None,
        prefect_client: PrefectClient,
        http_requests: pytest.LogCaptureFixture,
    ) -> None:
        deployment = await prefect_client.read_deployment_by_name(name=DUMMY_FLOW.full_name)
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        http_requests.clear()

        await self.submit_dummy(service=service, priority=WorkflowPriority.MEDIUM)
        saved_id = await DUMMY_FLOW.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)
        run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.MEDIUM)

        assert saved_id == deployment.id
        assert dispatch_requests(caplog=http_requests) == [
            lookup(workflow=DUMMY_FLOW),
            create(deployment_id=deployment.id),
            create(deployment_id=deployment.id),
        ]
        run = await prefect_client.read_flow_run(flow_run_id=run_id)
        assert run.deployment_id == deployment.id

    async def test_dispatch_to_recreated_deployment_looks_it_up_again(
        self,
        dispatch_deployments: None,
        prefect_client: PrefectClient,
        http_requests: pytest.LogCaptureFixture,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        await self.submit_dummy(service=service, priority=WorkflowPriority.MEDIUM)
        deleted = await prefect_client.read_deployment_by_name(name=DUMMY_FLOW.full_name)
        await prefect_client.delete_deployment(deployment_id=deleted.id)
        recreated_id = await DUMMY_FLOW.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)
        assert recreated_id != deleted.id
        http_requests.clear()

        run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)

        assert dispatch_requests(caplog=http_requests) == [
            create(deployment_id=deleted.id, status=404),
            lookup(workflow=DUMMY_FLOW),
            create(deployment_id=recreated_id),
        ]
        run = await prefect_client.read_flow_run(flow_run_id=run_id)
        assert (run.deployment_id, run.work_queue_name) == (recreated_id, WorkflowPriority.HIGH.queue_name)

    async def test_dispatch_of_missing_deployment_creates_no_run(
        self,
        dispatch_deployments: None,
        prefect_client: PrefectClient,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        runs_before = await prefect_client.count_flow_runs()

        with pytest.raises(ObjectNotFound):
            await service.submit_workflow(
                workflow=UNKNOWN_WORKFLOW, parameters={"data": DummyInput(firstname="John", lastname="Doe")}
            )

        assert await prefect_client.count_flow_runs() == runs_before

    async def test_dispatch_from_inside_a_flow_is_linked_as_its_subflow(
        self,
        dispatch_deployments: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        child_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_CHILD)
        workflow_info = await service.submit_workflow(
            workflow=PRIORITY_PARENT, context=build_context(), priority=WorkflowPriority.HIGH
        )
        parent_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=parent_run)

        child_run = await self.wait_for_dispatched_run(
            client=prefect_client, workflow=PRIORITY_CHILD, seen_ids=child_seen
        )
        assert child_run.work_queue_name == WorkflowPriority.HIGH.queue_name
        assert child_run.parent_task_run_id is not None
        parent_task_run = await prefect_client.read_task_run(task_run_id=child_run.parent_task_run_id)
        assert parent_task_run.flow_run_id == parent_run.id

    async def test_blocking_dispatch_from_inside_a_flow_is_linked_as_its_subflow(
        self,
        dispatch_deployments: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        child_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_GRANDCHILD)
        workflow_info = await service.submit_workflow(
            workflow=PRIORITY_PARENT_BLOCKING, context=build_context(), priority=WorkflowPriority.LOW
        )
        parent_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)

        # The parent blocks on its child's result, so it runs in a background task
        # while the test drives the child run through the worker.
        parent_task = asyncio.create_task(
            self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=parent_run)
        )
        try:
            child_run = await self.wait_for_dispatched_run(
                client=prefect_client, workflow=PRIORITY_GRANDCHILD, seen_ids=child_seen
            )
            await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=child_run)
            await asyncio.wait_for(parent_task, timeout=60)
        finally:
            if not parent_task.done():
                parent_task.cancel()
                with suppress(asyncio.CancelledError):
                    await parent_task

        assert child_run.work_queue_name == WorkflowPriority.LOW.queue_name
        assert child_run.parent_task_run_id is not None
        parent_task_run = await prefect_client.read_task_run(task_run_id=child_run.parent_task_run_id)
        assert parent_task_run.flow_run_id == parent_run.id
