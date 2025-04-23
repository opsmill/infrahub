import pytest
from prefect.client.orchestration import PrefectClient

from infrahub.workflows.constants import WorkflowType
from infrahub.workflows.initialization import setup_task_manager
from infrahub.workflows.models import WorkerPoolDefinition
from tests.helpers.test_worker import TestWorkerInfrahubAsync, TestWorkerProcess


@pytest.fixture(scope="module")
def infrahubasync_worker() -> WorkerPoolDefinition:
    return WorkerPoolDefinition(
        name="infrahub-worker",
        workflow_type=WorkflowType.INTERNAL | WorkflowType.CORE | WorkflowType.USER,
        description="Default Pool for internal tasks",
    )


@pytest.fixture(scope="module")
def user_worker() -> WorkerPoolDefinition:
    return WorkerPoolDefinition(
        name="user-task-worker", workflow_type=WorkflowType.USER, description="Default Pool for user tasks"
    )


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
