import asyncio
from contextlib import ExitStack
from typing import Any, Generator
from uuid import UUID

import pytest
from infrahub_sdk import InfrahubClient
from prefect import settings as prefect_settings
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterId
from prefect.client.schemas.objects import FlowRun, StateType, WorkPool
from prefect.workers.base import BaseWorkerResult
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub.tasks.dummy import DUMMY_FLOW, DUMMY_FLOW_BROKEN
from infrahub.workers.infrahub_async import (
    InfrahubWorkerAsync,
)
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.initialization import setup_blocks
from infrahub.workflows.models import WorkerPoolDefinition
from tests.helpers.constants import (
    INFRAHUB_USE_TEST_CONTAINERS,
    PORT_PREFECT,
)
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.utils import get_exposed_port


class TestWorkerInfrahubAsync(TestInfrahubApp):
    @classmethod
    async def wait_for_flow(
        cls, client: PrefectClient, work_pool_id: UUID, interval: int = 1, timeout: int = 10
    ) -> FlowRun:
        while timeout:
            flows = await client.read_flow_runs(
                work_pool_filter=WorkPoolFilter(id=WorkPoolFilterId(any_=[work_pool_id]))
            )

            scheduled_flows = [flow for flow in flows if flow.state_type in [StateType.SCHEDULED]]
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
    def prefect_container(
        self, request: pytest.FixtureRequest, load_settings_before_session: Any
    ) -> dict[int, int] | None:
        if not INFRAHUB_USE_TEST_CONTAINERS:
            return None

        container = (
            DockerContainer(image="prefecthq/prefect:3.0.3-python3.12")
            .with_command("prefect server start --host 0.0.0.0 --ui")
            .with_exposed_ports(PORT_PREFECT)
        )

        def cleanup() -> None:
            container.stop()

        container.start()
        wait_for_logs(container, "Configure Prefect to communicate with the server")
        request.addfinalizer(cleanup)

        return {PORT_PREFECT: get_exposed_port(container, PORT_PREFECT)}

    @pytest.fixture(scope="class")
    def prefect_server(
        self, prefect_container: dict[int, int] | None, reload_settings_before_each_module: Any
    ) -> Generator[str, None, None]:
        if prefect_container:
            server_port = prefect_container[PORT_PREFECT]
            server_api_url = f"http://localhost:{server_port}/api"
        else:
            server_api_url = f"http://localhost:{PORT_PREFECT}/api"

        with ExitStack() as stack:
            stack.enter_context(
                prefect_settings.temporary_settings(
                    updates={
                        prefect_settings.PREFECT_API_URL: server_api_url,
                    }
                )
            )
            yield server_api_url

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_server: str) -> PrefectClient:
        return PrefectClient(api=prefect_server)

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
        self, client: InfrahubClient, block_storage: Any, prefect_client: PrefectClient, work_pool: WorkPool
    ) -> InfrahubWorkerAsync:
        worker = InfrahubWorkerAsync(work_pool_name=work_pool.name)

        await worker.setup(client=client, metric_port=0)
        await worker.sync_with_backend()

        # Validate that the worker has properly registered with the server
        active_workers = await prefect_client.read_workers_for_work_pool(work_pool_name=work_pool.name)
        assert active_workers[0].name == worker.name

        return worker
