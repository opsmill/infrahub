import pytest
from prefect.logging.loggers import disable_run_logger
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session")
def prefect_server_in_memory():
    with prefect_test_harness(server_startup_timeout=60):
        yield

