import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import WorkPool
from prefect.client.schemas.schedules import CronSchedule

from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workflows.catalogue import CLEAN_UP_DEADLOCKS, INFRAHUB_WORKER_POOL
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.initialization import setup_work_queues
from tests.helpers.test_worker import TestWorkerInfrahubAsync


class TestWorkflowPriority(TestWorkerInfrahubAsync):
    @pytest.fixture(scope="class")
    async def priority_work_queues(self, work_pool: WorkPool, prefect_client: PrefectClient) -> None:
        await setup_work_queues(client=prefect_client)

    @pytest.fixture(scope="class")
    async def priority_deployments(self, priority_work_queues: None, prefect_client: PrefectClient) -> None:
        for workflow in [DUMMY_FLOW, CLEAN_UP_DEADLOCKS]:
            await workflow.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)

    async def test_setup_creates_priority_queues_with_converged_precedence(
        self,
        priority_work_queues: None,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ) -> None:
        queues = await prefect_client.read_work_queues(work_pool_name=work_pool.name)
        precedences = {queue.name: queue.priority for queue in queues}

        assert precedences["high"] == 1
        assert precedences["medium"] == 2
        assert precedences["low"] == 3
        # The server assigns the built-in default queue a precedence as a side effect of
        # inserting the three pinned queues; only its relative position is guaranteed.
        assert precedences["default"] > precedences["low"]

    @pytest.mark.parametrize("priority", [pytest.param(priority, id=priority.value) for priority in WorkflowPriority])
    async def test_dispatch_with_explicit_priority_lands_in_matching_queue(
        self,
        priority: WorkflowPriority,
        priority_deployments: None,
        prefect_client: PrefectClient,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())

        workflow_info = await service.submit_workflow(
            workflow=DUMMY_FLOW,
            parameters={"data": DummyInput(firstname="John", lastname="Doe")},
            priority=priority,
        )

        flow_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)
        assert flow_run.work_queue_name == priority.queue_name

    async def test_dispatch_without_priority_lands_in_medium_queue(
        self,
        priority_deployments: None,
        prefect_client: PrefectClient,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())

        workflow_info = await service.submit_workflow(
            workflow=DUMMY_FLOW,
            parameters={"data": DummyInput(firstname="John", lastname="Doe")},
        )

        flow_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)
        assert flow_run.work_queue_name == WorkflowPriority.MEDIUM.queue_name

    async def test_cron_deployment_attached_to_tier_queue_with_schedule_intact(
        self,
        priority_deployments: None,
        prefect_client: PrefectClient,
    ) -> None:
        deployment = await prefect_client.read_deployment_by_name(name=CLEAN_UP_DEADLOCKS.full_name)

        assert deployment.work_queue_name == CLEAN_UP_DEADLOCKS.default_priority.queue_name
        assert len(deployment.schedules) == 1
        schedule = deployment.schedules[0].schedule
        assert isinstance(schedule, CronSchedule)
        assert schedule.cron == CLEAN_UP_DEADLOCKS.cron
