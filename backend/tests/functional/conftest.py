from collections.abc import Generator

import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_test_fixture() -> Generator[None]:
    with prefect_test_harness(server_startup_timeout=60):
        yield
