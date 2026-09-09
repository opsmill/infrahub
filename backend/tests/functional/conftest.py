import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from prefect.server.api.server import SubprocessASGIServer
from prefect.testing.utilities import prefect_test_harness

from infrahub import config
from tests.helpers.constants import (
    PREFECT_FLOW_HEARTBEAT_FREQUENCY_SECONDS,
    PREFECT_SERVER_NONESSENTIAL_SERVICE_ENV_VARS,
    PREFECT_TEST_SERVER_PORT_RANGE,
)
from tests.helpers.utils import find_available_prefect_port


@pytest.fixture(scope="session", autouse=True)
def prefect_test_fixture() -> Generator[None]:
    os.environ["PREFECT_FLOWS_HEARTBEAT_FREQUENCY"] = PREFECT_FLOW_HEARTBEAT_FREQUENCY_SECONDS
    os.environ.update(PREFECT_SERVER_NONESSENTIAL_SERVICE_ENV_VARS)

    with (
        patch.object(SubprocessASGIServer, "_port_range", PREFECT_TEST_SERVER_PORT_RANGE),
        patch("prefect.testing.utilities._find_available_port", find_available_prefect_port),
        prefect_test_harness(server_startup_timeout=60),
    ):
        yield


@pytest.fixture
def delete_branch_after_merge_reset_config() -> Generator[None]:
    original = config.SETTINGS.main.delete_branch_after_merge
    yield
    config.SETTINGS.main.delete_branch_after_merge = original


@pytest.fixture
def delete_git_branch_after_merge_reset_config() -> Generator[None]:
    original = config.SETTINGS.git.delete_git_branch_after_merge
    yield
    config.SETTINGS.git.delete_git_branch_after_merge = original
