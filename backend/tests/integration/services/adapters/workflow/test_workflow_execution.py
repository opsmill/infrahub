import asyncio

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import WorkPool
from pydantic import ValidationError

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DUMMY_FLOW_BROKEN, DummyInput, DummyOutput
from infrahub.workers.infrahub_async import (
    InfrahubWorkerAsync,
)
from tests.helpers.test_worker import TestWorkerInfrahubAsync


class TestWorkflowExecution(TestWorkerInfrahubAsync):
    async def test_execute_workflow_success(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
        dummy_flows_deployment,
        work_pool: WorkPool,
        client,
    ):
        service = WorkflowWorkerExecution()

        task = asyncio.create_task(
            service.execute_workflow(
                workflow=DUMMY_FLOW, parameters={"data": DummyInput(firstname="John", lastname="Doe")}
            )
        )

        # Wait for the flow to show up in Prefect
        flow = await self.wait_for_flow(client=prefect_client, work_pool_id=work_pool.id)

        # Execute the flow
        worker_result = await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=flow)
        assert worker_result.status_code == 0

        result = await task
        assert isinstance(result, DummyOutput)
        assert result.full_name == "John, Doe"

    async def test_execute_workflow_failure(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
        dummy_flows_deployment,
        work_pool: WorkPool,
        client,
    ):
        service = WorkflowWorkerExecution()

        task = asyncio.create_task(
            service.execute_workflow(
                workflow=DUMMY_FLOW_BROKEN, parameters={"data": DummyInput(firstname="John", lastname="Doe")}
            )
        )

        # Wait for the flow to show up in Prefect
        flow = await self.wait_for_flow(client=prefect_client, work_pool_id=work_pool.id)

        # Execute the flow
        worker_result = await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=flow)
        assert worker_result.status_code == 0

        with pytest.raises(ValidationError) as exc:
            await task

        assert "validation error for DummyOutput" in str(exc.value)
