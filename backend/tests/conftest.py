import asyncio
import importlib
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

import pytest
import ujson
from infrahub_sdk import UUIDT
from infrahub_sdk.utils import str_to_bool

from infrahub import config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.initialization import (
    create_default_branch,
    create_global_branch,
    create_root_node,
)
from infrahub.core.schema import (
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema_manager import SchemaBranch, SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.lock import initialize_lock
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, Meta
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus

BUILD_NAME = os.environ.get("INFRAHUB_BUILD_NAME", "infrahub")
TEST_IN_DOCKER = str_to_bool(os.environ.get("INFRAHUB_TEST_IN_DOCKER", "false"))
ResponseClass = TypeVar("ResponseClass")


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


@pytest.fixture(scope="module")
async def db() -> InfrahubDatabase:
    driver = InfrahubDatabase(driver=await get_db(retry=1))

    yield driver

    await driver.close()


@pytest.fixture
async def empty_database(db: InfrahubDatabase) -> None:
    await delete_all_nodes(db=db)
    await create_root_node(db=db)


@pytest.fixture
async def reset_registry(db: InfrahubDatabase) -> None:
    registry.delete_all()


@pytest.fixture
async def default_branch(reset_registry, local_storage_dir, empty_database, db: InfrahubDatabase) -> Branch:
    branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()
    return branch


@pytest.fixture
def local_storage_dir(tmp_path) -> str:
    storage_dir = os.path.join(str(tmp_path), "storage")
    os.mkdir(storage_dir)

    config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
    config.SETTINGS.storage.local.path_ = storage_dir

    return storage_dir


@pytest.fixture
async def register_internal_models_schema(default_branch: Branch) -> SchemaBranch:
    schema = SchemaRoot(**internal_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture
async def register_core_models_schema(default_branch: Branch, register_internal_models_schema) -> SchemaBranch:
    schema = SchemaRoot(**core_models)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture(scope="module", autouse=True)
def execute_before_any_test(worker_id, tmpdir_factory):
    config.load_and_exit()

    config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage

    if TEST_IN_DOCKER:
        try:
            db_id = int(worker_id[2]) + 1
        except (ValueError, IndexError):
            db_id = 1

        config.SETTINGS.cache.address = f"{BUILD_NAME}-cache-{db_id}"
        config.SETTINGS.database.address = f"{BUILD_NAME}-database-{db_id}"
        config.SETTINGS.broker.address = f"{BUILD_NAME}-message-queue-{db_id}"
        config.SETTINGS.storage.local = config.FileSystemStorageSettings(path="/opt/infrahub/storage")
    else:
        storage_dir = tmpdir_factory.mktemp("storage")
        config.SETTINGS.storage.local._path = str(storage_dir)

    config.SETTINGS.broker.enable = False
    config.SETTINGS.cache.enable = True
    config.SETTINGS.miscellaneous.start_background_runner = False
    config.SETTINGS.security.secret_key = "4e26b3d9-b84f-42c9-a03f-fee3ada3b2fa"
    config.SETTINGS.main.internal_address = "http://mock"
    config.OVERRIDE.message_bus = BusRecorder()

    initialize_lock()


@pytest.fixture
async def data_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    SCHEMA = {
        "generics": [
            {
                "name": "Owner",
                "namespace": "Lineage",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "Source",
                "description": "Any Entities that stores or produces data.",
                "namespace": "Lineage",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def group_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA = {
        "generics": [
            {
                "name": "Group",
                "namespace": "Core",
                "description": "Generic Group Object.",
                "label": "Group",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
        ],
        "nodes": [
            {
                "name": "StandardGroup",
                "namespace": "Core",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.GENERICGROUP],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def car_person_schema(db: InfrahubDatabase, default_branch: Branch, node_group_schema, data_schema) -> None:
    SCHEMA = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                    {"name": "is_electric", "kind": "Boolean"},
                    {
                        "name": "transmission",
                        "kind": "Text",
                        "optional": True,
                        "enum": ["manual", "automatic", "flintstone-feet"],
                    },
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "optional": False,
                        "cardinality": "one",
                        "direction": "outbound",
                    },
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many", "direction": "inbound"}],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def node_group_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA = {
        "generics": [
            {
                "name": "Node",
                "namespace": "Core",
                "description": "Base Node in Infrahub.",
                "label": "Node",
            },
            {
                "name": "Group",
                "namespace": "Core",
                "description": "Generic Group Object.",
                "label": "Group",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "members",
                        "peer": "CoreNode",
                        "optional": True,
                        "identifier": "group_member",
                        "cardinality": "many",
                    },
                    {
                        "name": "subscribers",
                        "peer": "CoreNode",
                        "optional": True,
                        "identifier": "group_subscriber",
                        "cardinality": "many",
                    },
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


class BusRPCMock(InfrahubMessageBus):
    def __init__(self):
        self.response: List[InfrahubResponse] = []
        self.messages: List[InfrahubMessage] = []

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        self.messages.append(message)

    def add_mock_reply(self, response: InfrahubResponse):
        self.response.append(response)

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        self.messages.append(message)
        return self.response.pop()


class BusRecorder(InfrahubMessageBus):
    def __init__(self, component_type: Optional[ComponentType] = None):
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
    def __init__(self, database: Optional[InfrahubDatabase] = None):
        self.messages: List[InfrahubMessage] = []
        self.messages_per_routing_key: Dict[str, List[InfrahubMessage]] = {}
        self.service: InfrahubServices = InfrahubServices(database=database, message_bus=self)
        self.replies: Dict[str, List[InfrahubResponse]] = defaultdict(list)

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)
        await execute_message(routing_key=routing_key, message_body=message.body, service=self.service)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        correlation_id = message.meta.correlation_id or "default"
        self.replies[correlation_id].append(message)

    async def rpc(self, message: InfrahubMessage, response_class: ResponseClass) -> ResponseClass:  # type: ignore[override]
        routing_key = ROUTING_KEY_MAP.get(type(message))

        correlation_id = str(UUIDT())
        message.meta = Meta(correlation_id=correlation_id, reply_to="ci-testing")

        await self.publish(message=message, routing_key=routing_key)
        reply_id = correlation_id or "default"
        assert len(self.replies[reply_id]) == 1
        response = self.replies[reply_id][0]
        data = ujson.loads(response.body)
        return response_class(**data)  # type: ignore[operator]

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
    def get_message_bus_simulator(db: Optional[InfrahubDatabase] = None) -> BusSimulator:
        return BusSimulator(database=db)

    @staticmethod
    def get_message_bus_rpc() -> BusRPCMock:
        return BusRPCMock()


class FakeLogger:
    def __init__(self) -> None:
        self.info_logs: List[Optional[str]] = []
        self.error_logs: List[Optional[str]] = []

    def debug(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a debug event"""

    def info(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        self.info_logs.append(event)

    def warning(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    def error(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""
        self.error_logs.append(event)

    def critical(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    def exception(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""


@pytest.fixture()
def fake_log() -> FakeLogger:
    return FakeLogger()


@pytest.fixture()
def helper() -> TestHelper:
    return TestHelper()
