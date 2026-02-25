from collections.abc import Generator

from infrahub.telemetry.task_manager import gather_prefect_information


async def test_gather_prefect_information(prefect_test_fixture: Generator) -> None:
    data = await gather_prefect_information()
    assert data
