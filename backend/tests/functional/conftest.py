import pytest
from prefect.logging.loggers import disable_run_logger
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_test_fixture():
    with prefect_test_harness():
        yield


@pytest.fixture(scope="session")
def prefect_test(prefect_test_fixture):
    with disable_run_logger():
        yield
