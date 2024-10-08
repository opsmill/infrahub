from typing import AsyncGenerator

import pytest
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.workflows.initialization import setup_task_manager


@pytest.fixture
async def prefect_server(redis, prefect):
    await setup_task_manager()


@pytest.fixture
async def prefect_client(prefect) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client
