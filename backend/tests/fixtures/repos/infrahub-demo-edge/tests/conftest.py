import os
from pathlib import Path
from typing import Tuple

import pytest
import ujson
from infrahub_sdk import InfrahubClientSync


class TestHelper:
    """TestHelper profiles functions that can be used as a fixture throughout the test framework"""

    @staticmethod
    def fixture_file(file_name: str) -> dict:
        """Return the contents of a fixture file as a dictionary"""
        file_content = Path(os.path.join(TestHelper.get_fixtures_dir(), file_name)).read_text()

        return ujson.loads(file_content)

    @staticmethod
    def fixture_files(directory_name: str) -> Tuple[dict, dict]:
        """Return the contents of a schema file as a dictionary"""

        data_file = TestHelper.fixture_file(os.path.join(directory_name, "data.json"))

        if "data" in data_file:
            data_file = data_file["data"]

        response_file = TestHelper.fixture_file(os.path.join(directory_name, "response.json"))

        return (data_file, response_file)

    @staticmethod
    def get_fixtures_dir():
        """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
        here = os.path.abspath(os.path.dirname(__file__))
        fixtures_dir = os.path.join(here, "fixtures")

        return os.path.abspath(fixtures_dir)


@pytest.fixture()
def root_directory() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    root_dir = os.path.join(here, "../")
    return os.path.abspath(root_dir)


@pytest.fixture()
def helper() -> TestHelper:
    return TestHelper()


@pytest.fixture()
def client_sync() -> InfrahubClientSync:
    return InfrahubClientSync.init(address="http://localhost:8000", insert_tracker=True)
