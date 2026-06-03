from __future__ import annotations

import pytest
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import FlowRunWaitTimeout

from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workers.infrahub_async import InfrahubWorkerAsync
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL


@pytest.fixture(scope="module")
async def work_pool_and_deployment(prefect_test_fixture: None) -> None:
    async with get_client() as client:
        wp = WorkPoolCreate(
            name=INFRAHUB_WORKER_POOL.name,
            type=InfrahubWorkerAsync.type,
            description=INFRAHUB_WORKER_POOL.description,
        )
        await client.create_work_pool(work_pool=wp, overwrite=True)
        await DUMMY_FLOW.save(client=client, work_pool=INFRAHUB_WORKER_POOL)


async def test_execute_workflow_raises_when_no_worker_available(
    prefect_test_fixture: None,
    work_pool_and_deployment: None,
) -> None:
    """execute_workflow must raise when no worker picks up the submitted flow run within the timeout."""
    service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())

    with pytest.raises(FlowRunWaitTimeout):
        await service.execute_workflow(  # type: ignore[call-overload]
            workflow=DUMMY_FLOW,
            parameters={"data": DummyInput(firstname="Test", lastname="User")},
            timeout=1.0,
        )
