import asyncio
from typing import Any, AsyncGenerator
from uuid import UUID

import pytest
from infrahub_sdk import InfrahubClient
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterId
from prefect.client.schemas.objects import FlowRun, StateType, WorkPool
from prefect.events.worker import EventsWorker
from prefect.logging.handlers import APILogWorker
from prefect.results import _default_storages
from prefect.workers.base import BaseWorkerResult

from infrahub.tasks.dummy import DUMMY_FLOW, DUMMY_FLOW_BROKEN
from infrahub.workers.infrahub_async import (
    InfrahubWorkerAsync,
)
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.initialization import setup_blocks
from infrahub.workflows.models import WorkerPoolDefinition
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow


class TestWorkerInfrahubAsync(TestInfrahubAppWithoutLocalWorkflow):
    @classmethod
    async def wait_for_flow(
        cls, client: PrefectClient, work_pool_id: UUID, interval: int = 1, timeout: int = 10
    ) -> FlowRun:
        while timeout:
            flows = await client.read_flow_runs(
                work_pool_filter=WorkPoolFilter(id=WorkPoolFilterId(any_=[work_pool_id]))
            )

            scheduled_flows = [flow for flow in flows if flow.state_type == StateType.SCHEDULED]
            if scheduled_flows:
                return scheduled_flows[0]

            timeout = -interval
            await asyncio.sleep(interval)

        raise TimeoutError

    @classmethod
    async def worker_run_flow(
        cls, worker: InfrahubWorkerAsync, client: PrefectClient, flow: FlowRun
    ) -> BaseWorkerResult:
        assert flow.deployment_id
        deployment = await client.read_deployment(deployment_id=flow.deployment_id)
        flow_config = await worker._get_configuration(flow_run=flow, deployment=deployment)

        return await worker.run(
            flow_run=flow,
            configuration=flow_config,
        )

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_class: str) -> PrefectClient:
        return PrefectClient(api=prefect_class)

    @pytest.fixture(scope="class")
    async def work_pool(self, prefect_client: PrefectClient) -> WorkPool:
        wp = WorkPoolCreate(
            name=INFRAHUB_WORKER_POOL.name,
            type=InfrahubWorkerAsync.type,
            description=INFRAHUB_WORKER_POOL.name,
        )
        return await prefect_client.create_work_pool(work_pool=wp, overwrite=True)

    @pytest.fixture(scope="class")
    async def block_storage(self, redis: dict[int, int] | None, prefect_client: PrefectClient) -> None:
        await setup_blocks()

    @pytest.fixture(scope="class")
    async def dummy_flows_deployment(self, work_pool: WorkerPoolDefinition, prefect_client: PrefectClient) -> None:
        for flow in [DUMMY_FLOW, DUMMY_FLOW_BROKEN]:
            await flow.save(client=prefect_client, work_pool=INFRAHUB_WORKER_POOL)

    @pytest.fixture(scope="class")
    async def prefect_worker(
        self,
        client: InfrahubClient,
        block_storage: Any,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
        git_global_config_env_setting: Any,
    ) -> AsyncGenerator[InfrahubWorkerAsync, None]:
        worker = InfrahubWorkerAsync(work_pool_name=work_pool.name)

        await worker.setup(client=client, metric_port=0)
        await worker.sync_with_backend()

        # Validate that the worker has properly registered with the server
        active_workers = await prefect_client.read_workers_for_work_pool(work_pool_name=work_pool.name)
        assert active_workers[0].name == worker.name

        yield worker

        # Clear local worker instances to avoid issues with multiple test classes running in the same pytest worker
        EventsWorker.drain_all()
        APILogWorker.drain_all()

        # Clear local worker result storage cache
        _default_storages.clear()
