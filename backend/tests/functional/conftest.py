from collections.abc import Generator

import pytest
from prefect.testing.utilities import prefect_test_harness

from infrahub import config


@pytest.fixture(scope="session", autouse=True)
def prefect_test_fixture() -> Generator[None]:
    with prefect_test_harness(server_startup_timeout=60):
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
