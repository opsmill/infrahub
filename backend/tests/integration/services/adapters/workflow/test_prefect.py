from prefect.client.orchestration import get_client

from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.initialization import setup_task_manager


async def test_setup_task_manager(redis, prefect):
    await setup_task_manager()

    async with get_client(sync_client=False) as client:
        response = await client.read_work_pool(INFRAHUB_WORKER_POOL.name)
        assert response.type == INFRAHUB_WORKER_POOL.worker_type

    # Setup the task manager a second time to validate that it's idempotent
    await setup_task_manager()

    async with get_client(sync_client=False) as client:
        response = await client.read_work_pool(INFRAHUB_WORKER_POOL.name)
        assert response.type == INFRAHUB_WORKER_POOL.worker_type
