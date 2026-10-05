import asyncio
from uuid import UUID

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import StateType, WorkPool

from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workers.infrahub_async import SUBMISSION_WINDOW_CAPACITY, InfrahubWorkerAsync
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.initialization import setup_work_queues
from tests.helpers.test_worker import TestWorkerInfrahubAsync


class TestSubmissionWindow(TestWorkerInfrahubAsync):
    @pytest.fixture(scope="class")
    async def dummy_deployment_in_priority_queues(self, work_pool: WorkPool, prefect_client: PrefectClient) -> None:
        await setup_work_queues(client=prefect_client)
        await DUMMY_FLOW.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)

    @classmethod
    async def submit_dummy(cls, service: WorkflowWorkerExecution, priority: WorkflowPriority) -> UUID:
        workflow_info = await service.submit_workflow(
            workflow=DUMMY_FLOW,
            parameters={"data": DummyInput(firstname="John", lastname="Doe")},
            priority=priority,
        )
        return workflow_info.id

    async def test_poll_claims_the_high_priority_run_first_and_drains_the_rest_without_polling_again(
        self,
        dummy_deployment_in_priority_queues: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        low_ids = [
            await self.submit_dummy(service=service, priority=WorkflowPriority.LOW)
            for _ in range(SUBMISSION_WINDOW_CAPACITY + 4)
        ]
        high_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)

        submitted = await prefect_worker.get_and_submit_flow_runs()

        assert len(submitted) == SUBMISSION_WINDOW_CAPACITY
        assert submitted[0].id == high_id

        all_ids = [high_id, *low_ids]
        async with asyncio.timeout(60):
            while True:
                runs = await prefect_client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=all_ids))
                )
                if all(run.state_type == StateType.COMPLETED for run in runs):
                    break
                await asyncio.sleep(1)

    async def test_submitted_run_records_no_infrastructure_id(
        self,
        dummy_deployment_in_priority_queues: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        flow_run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)

        submitted = await prefect_worker.get_and_submit_flow_runs()

        assert flow_run_id in {run.id for run in submitted}
        async with asyncio.timeout(60):
            while True:
                run = await prefect_client.read_flow_run(flow_run_id)
                if run.state_type == StateType.COMPLETED:
                    break
                await asyncio.sleep(1)
        assert run.infrastructure_pid is None

    async def test_submitted_run_goes_from_pending_to_running(
        self,
        dummy_deployment_in_priority_queues: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        flow_run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)

        submitted = await prefect_worker.get_and_submit_flow_runs()

        assert flow_run_id in {run.id for run in submitted}
        async with asyncio.timeout(60):
            while True:
                run = await prefect_client.read_flow_run(flow_run_id)
                if run.state_type == StateType.COMPLETED:
                    break
                await asyncio.sleep(1)
        states = await prefect_client.read_flow_run_states(flow_run_id)
        assert [state.name for state in states] == ["Scheduled", "Pending", "Running", "Completed"]

    async def test_submitted_run_gets_no_worker_labels(
        self,
        dummy_deployment_in_priority_queues: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        flow_run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)

        submitted = await prefect_worker.get_and_submit_flow_runs()

        assert flow_run_id in {run.id for run in submitted}
        async with asyncio.timeout(60):
            while True:
                run = await prefect_client.read_flow_run(flow_run_id)
                if run.state_type == StateType.COMPLETED:
                    break
                await asyncio.sleep(1)
        assert not [label for label in run.labels if label.startswith(("prefect.worker.", "prefect.work-pool."))]
