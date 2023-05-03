import asyncio
import os
from pathlib import Path

import pytest
import ujson

import infrahub.config as config

TEST_DATABASE = "infrahub.testing"


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def execute_before_any_test():
    config.load_and_exit()
    config.SETTINGS.database.database = TEST_DATABASE
    config.SETTINGS.broker.enable = False
    config.SETTINGS.main.internal_address = "http://mock"


class TestHelper:
    """TestHelper profiles functions that can be used as a fixture throughout the test framework"""

    @staticmethod
    def schema_file(file_name: str) -> dict:
        """Return the contents of a schema file as a dictionary"""
        file_content = Path(os.path.join(TestHelper.get_fixtures_dir(), f"schemas/{file_name}")).read_text()

        return ujson.loads(file_content)

    @staticmethod
    def get_fixtures_dir():
        """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
        here = os.path.abspath(os.path.dirname(__file__))
        fixtures_dir = os.path.join(here, "fixtures")

        return os.path.abspath(fixtures_dir)


@pytest.fixture()
def helper() -> TestHelper:
    return TestHelper()
