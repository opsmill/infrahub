from uuid import UUID

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterDeploymentId
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.client.schemas.schedules import CronSchedule

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workers.infrahub_async import InfrahubWorkerAsync
from infrahub.workflows.catalogue import CLEAN_UP_DEADLOCKS, INFRAHUB_WORKER_POOL
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.initialization import setup_work_queues
from infrahub.workflows.models import WorkflowDefinition
from tests.helpers.test_worker import TestWorkerInfrahubAsync
from tests.integration.services.adapters.workflow.fixture_flows import (
    PRIORITY_CHILD,
    PRIORITY_FIXTURE_WORKFLOWS,
    PRIORITY_GRANDCHILD,
    PRIORITY_LEAF_HIGH_DEFAULT,
    PRIORITY_PARENT,
    PRIORITY_PARENT_HIGH_DEFAULT_CHILD,
    PRIORITY_PARENT_OVERRIDING,
)


def build_context() -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name="main", id="1111aaaa-0000-0000-0000-000000000000"),
        account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="account-a"),
    )


class TestWorkflowPriority(TestWorkerInfrahubAsync):
    @pytest.fixture(scope="class")
    async def priority_work_queues(self, work_pool: WorkPool, prefect_client: PrefectClient) -> None:
        await setup_work_queues(client=prefect_client)

    @pytest.fixture(scope="class")
    async def priority_deployments(self, priority_work_queues: None, prefect_client: PrefectClient) -> None:
        for workflow in [DUMMY_FLOW, CLEAN_UP_DEADLOCKS, *PRIORITY_FIXTURE_WORKFLOWS]:
            await workflow.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)

    @classmethod
    async def deployment_run_ids(cls, client: PrefectClient, workflow: WorkflowDefinition) -> set[UUID]:
        deployment = await client.read_deployment_by_name(name=workflow.full_name)
        runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(deployment_id=FlowRunFilterDeploymentId(any_=[deployment.id]))
        )
        return {run.id for run in runs}

    @classmethod
    async def dispatched_run(cls, client: PrefectClient, workflow: WorkflowDefinition, seen_ids: set[UUID]) -> FlowRun:
        """Return the single flow run of the deployment that appeared since ``seen_ids`` was captured."""
        new_ids = await cls.deployment_run_ids(client=client, workflow=workflow) - seen_ids
        assert len(new_ids) == 1
        return await client.read_flow_run(flow_run_id=new_ids.pop())

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

    async def test_root_priority_inherited_by_context_only_descendants(
        self,
        priority_deployments: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        child_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_CHILD)
        grandchild_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_GRANDCHILD)

        workflow_info = await service.submit_workflow(
            workflow=PRIORITY_PARENT, context=build_context(), priority=WorkflowPriority.HIGH
        )
        parent_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)
        assert parent_run.work_queue_name == WorkflowPriority.HIGH.queue_name

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=parent_run)
        child_run = await self.dispatched_run(client=prefect_client, workflow=PRIORITY_CHILD, seen_ids=child_seen)
        assert child_run.work_queue_name == WorkflowPriority.HIGH.queue_name

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=child_run)
        grandchild_run = await self.dispatched_run(
            client=prefect_client, workflow=PRIORITY_GRANDCHILD, seen_ids=grandchild_seen
        )
        assert grandchild_run.work_queue_name == WorkflowPriority.HIGH.queue_name

    async def test_low_root_keeps_high_default_child_at_low(
        self,
        priority_deployments: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        leaf_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_LEAF_HIGH_DEFAULT)

        workflow_info = await service.submit_workflow(
            workflow=PRIORITY_PARENT_HIGH_DEFAULT_CHILD, context=build_context(), priority=WorkflowPriority.LOW
        )
        parent_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)
        assert parent_run.work_queue_name == WorkflowPriority.LOW.queue_name

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=parent_run)
        leaf_run = await self.dispatched_run(
            client=prefect_client, workflow=PRIORITY_LEAF_HIGH_DEFAULT, seen_ids=leaf_seen
        )
        assert leaf_run.work_queue_name == WorkflowPriority.LOW.queue_name

    async def test_explicit_override_mid_tree_reroots_its_subtree(
        self,
        priority_deployments: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        child_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_CHILD)
        grandchild_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_GRANDCHILD)

        workflow_info = await service.submit_workflow(
            workflow=PRIORITY_PARENT_OVERRIDING, context=build_context(), priority=WorkflowPriority.HIGH
        )
        parent_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)
        assert parent_run.work_queue_name == WorkflowPriority.HIGH.queue_name

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=parent_run)
        child_run = await self.dispatched_run(client=prefect_client, workflow=PRIORITY_CHILD, seen_ids=child_seen)
        assert child_run.work_queue_name == WorkflowPriority.LOW.queue_name

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=child_run)
        grandchild_run = await self.dispatched_run(
            client=prefect_client, workflow=PRIORITY_GRANDCHILD, seen_ids=grandchild_seen
        )
        assert grandchild_run.work_queue_name == WorkflowPriority.LOW.queue_name

    async def test_dispatch_tree_without_priority_lands_in_medium(
        self,
        priority_deployments: None,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
    ) -> None:
        service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
        child_seen = await self.deployment_run_ids(client=prefect_client, workflow=PRIORITY_CHILD)

        workflow_info = await service.submit_workflow(workflow=PRIORITY_PARENT, context=build_context())
        parent_run = await prefect_client.read_flow_run(flow_run_id=workflow_info.id)
        assert parent_run.work_queue_name == WorkflowPriority.MEDIUM.queue_name

        await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=parent_run)
        child_run = await self.dispatched_run(client=prefect_client, workflow=PRIORITY_CHILD, seen_ids=child_seen)
        assert child_run.work_queue_name == WorkflowPriority.MEDIUM.queue_name
