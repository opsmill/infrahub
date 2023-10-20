import asyncio
import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import ujson

from infrahub import config
from infrahub.lock import initialize_lock
from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub_client.utils import str_to_bool

BUILD_NAME = os.environ.get("INFRAHUB_BUILD_NAME", "infrahub")
TEST_IN_DOCKER = str_to_bool(os.environ.get("INFRAHUB_TEST_IN_DOCKER", "false"))


def pytest_addoption(parser):
    parser.addoption("--neo4j", action="store_true", dest="neo4j", default=False, help="enable neo4j tests")


def pytest_configure(config):
    if not config.option.neo4j:
        setattr(config.option, "markexpr", "not neo4j")


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def execute_before_any_test(worker_id):
    config.load_and_exit()
    initialize_lock()

    if TEST_IN_DOCKER:
        try:
            db_id = int(worker_id[2]) + 1
        except (ValueError, IndexError):
            db_id = 1

        config.SETTINGS.cache.address = f"{BUILD_NAME}-cache-1"
        config.SETTINGS.database.address = f"{BUILD_NAME}-database-{db_id}"
        config.SETTINGS.storage.settings = {"directory": "/opt/infrahub/storage"}

    config.SETTINGS.broker.enable = False
    config.SETTINGS.cache.enable = False
    config.SETTINGS.miscellaneous.start_background_runner = False
    config.SETTINGS.security.secret_key = "4e26b3d9-b84f-42c9-a03f-fee3ada3b2fa"
    config.SETTINGS.main.internal_address = "http://mock"


class BusRecorder(InfrahubMessageBus):
    def __init__(self):
        self.messages: List[InfrahubMessage] = []
        self.messages_per_routing_key: Dict[str, List[InfrahubMessage]] = {}

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)

    @property
    def seen_routing_keys(self) -> List[str]:
        return list(self.messages_per_routing_key.keys())


class BusSimulator(InfrahubMessageBus):
    def __init__(self):
        self.messages: List[InfrahubMessage] = []
        self.messages_per_routing_key: Dict[str, List[InfrahubMessage]] = {}
        self.service: InfrahubServices = InfrahubServices()
        self.replies: List[InfrahubMessage] = []

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)
        await execute_message(routing_key=routing_key, message_body=message.body, service=self.service)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        self.replies.append(message)

    @property
    def seen_routing_keys(self) -> List[str]:
        return list(self.messages_per_routing_key.keys())


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

    @staticmethod
    def import_module_in_fixtures(module: str) -> Any:
        """Import a python module from the fixtures directory."""

        sys.path.append(TestHelper.get_fixtures_dir())
        module_name = module.replace("/", ".")
        return importlib.import_module(module_name)

    @staticmethod
    def get_message_bus_recorder() -> BusRecorder:
        return BusRecorder()

    @staticmethod
    def get_message_bus_simulator() -> BusSimulator:
        return BusSimulator()


@pytest.fixture()
def helper() -> TestHelper:
    return TestHelper()
