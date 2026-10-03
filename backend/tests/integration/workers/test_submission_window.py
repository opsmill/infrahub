import asyncio
from uuid import UUID

import anyio
import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import StateType, WorkPool

from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workers.infrahub_async import SUBMISSION_WINDOW_CAPACITY, InfrahubWorkerAsync
from infrahub.workers.submission import SubmissionWindow
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.initialization import setup_work_queues
from tests.helpers.flow_run_reservations import UnreachableReservations
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

    @classmethod
    async def wait_for_completion(cls, prefect_client: PrefectClient, flow_run_ids: list[UUID]) -> None:
        async with asyncio.timeout(60):
            while True:
                runs = await prefect_client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=flow_run_ids))
                )
                if len(runs) == len(flow_run_ids) and all(run.state_type == StateType.COMPLETED for run in runs):
                    return
                await asyncio.sleep(1)

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

        assert [flow_run.id for flow_run in submitted] == [high_id, *low_ids[: SUBMISSION_WINDOW_CAPACITY - 1]]

        await self.wait_for_completion(prefect_client=prefect_client, flow_run_ids=[high_id, *low_ids])

    async def test_poll_with_unreachable_reservations_leaves_its_runs_scheduled_for_the_next_poll(
        self,
        dummy_deployment_in_priority_queues: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        run_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)

        window = prefect_worker._submission_window
        prefect_worker._submission_window = SubmissionWindow(
            capacity=SUBMISSION_WINDOW_CAPACITY, reservations=UnreachableReservations()
        )
        try:
            assert await prefect_worker.get_and_submit_flow_runs() == []
            assert prefect_worker._submission_window.in_flight == 0
        finally:
            prefect_worker._submission_window = window

        run = await prefect_client.read_flow_run(flow_run_id=run_id)
        assert run.state_type == StateType.SCHEDULED

        assert [flow_run.id for flow_run in await prefect_worker.get_and_submit_flow_runs()] == [run_id]
        await self.wait_for_completion(prefect_client=prefect_client, flow_run_ids=[run_id])

    async def test_poll_meeting_a_run_that_holds_a_limit_slot_frees_only_the_slots_it_did_not_submit(
        self,
        dummy_deployment_in_priority_queues: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        submitted_id = await self.submit_dummy(service=service, priority=WorkflowPriority.HIGH)
        executing_id = await self.submit_dummy(service=service, priority=WorkflowPriority.LOW)
        limiter = anyio.CapacityLimiter(SUBMISSION_WINDOW_CAPACITY)
        limiter.acquire_on_behalf_of_nowait(executing_id)

        prefect_worker._limiter = limiter
        try:
            # The second run already holds a limit slot, so Prefect raises after handing over the first run.
            assert await prefect_worker.get_and_submit_flow_runs() == []
            assert prefect_worker._submission_window.in_flight == 1
        finally:
            prefect_worker._limiter = None

        await self.wait_for_completion(prefect_client=prefect_client, flow_run_ids=[submitted_id])
        assert prefect_worker._submission_window.in_flight == 0

        assert [flow_run.id for flow_run in await prefect_worker.get_and_submit_flow_runs()] == [executing_id]
        await self.wait_for_completion(prefect_client=prefect_client, flow_run_ids=[executing_id])
