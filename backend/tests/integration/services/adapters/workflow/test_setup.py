from prefect.client.orchestration import PrefectClient

from infrahub.workflows.initialization import setup_task_manager
from infrahub.workflows.models import WorkerPoolDefinition
from tests.helpers.test_worker import TestWorkerInfrahubAsync

# @pytest.fixture
# async def prefect_server(redis, prefect):
#     await setup_task_manager()


class TestTaskManagerSetup(TestWorkerInfrahubAsync):
    async def test_setup_task_manager(self, infrahubasync_worker: WorkerPoolDefinition, prefect_client: PrefectClient):
        await setup_task_manager()

        response = await prefect_client.read_work_pool(infrahubasync_worker.name)
        assert response.type == "infrahubasync"

        # Setup the task manager a second time to validate that it's idempotent
        await setup_task_manager()

        response = await prefect_client.read_work_pool(infrahubasync_worker.name)
        assert response.type == "infrahubasync"
