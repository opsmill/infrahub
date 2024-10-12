from prefect.client.orchestration import PrefectClient

from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.initialization import setup_task_manager
from tests.helpers.test_worker import TestWorkerInfrahubAsync

# @pytest.fixture
# async def prefect_server(redis, prefect):
#     await setup_task_manager()


class TestTaskManagerSetup(TestWorkerInfrahubAsync):
    async def test_setup_task_manager(self, prefect_client: PrefectClient):
        await setup_task_manager()

        response = await prefect_client.read_work_pool(INFRAHUB_WORKER_POOL.name)
        assert response.type == INFRAHUB_WORKER_POOL.worker_type

        # Setup the task manager a second time to validate that it's idempotent
        await setup_task_manager()

        response = await prefect_client.read_work_pool(INFRAHUB_WORKER_POOL.name)
        assert response.type == INFRAHUB_WORKER_POOL.worker_type
