import asyncio
import importlib
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, AsyncGenerator, Generator, Optional, TypeVar

import pytest
import ujson
from infrahub_sdk.utils import str_to_bool
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from prefect.logging.loggers import disable_run_logger
from prefect.testing.utilities import prefect_test_harness
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub import config
from infrahub.config import load_and_exit
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.initialization import (
    create_default_branch,
    create_global_branch,
    create_ipam_namespace,
    create_root_node,
)
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.lock import initialize_lock
from infrahub.message_bus import InfrahubMessage, InfrahubResponse
from infrahub.message_bus.types import MessageTTL
from infrahub.services import services
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from tests.adapters.log import FakeLogger
from tests.adapters.message_bus import BusRecorder, BusSimulator

ResponseClass = TypeVar("ResponseClass")
INFRAHUB_USE_TEST_CONTAINERS = str_to_bool(os.getenv("INFRAHUB_USE_TEST_CONTAINERS", "true"))
PORT_NATS = 4222
PORT_REDIS = 6379
PORT_CLIENT_RABBITMQ = 5672
PORT_HTTP_RABBITMQ = 15672
PORT_BOLT_NEO4J = 7687
PORT_MEMGRAPH = 7687


def pytest_addoption(parser):
    parser.addoption("--neo4j", action="store_true", dest="neo4j", default=False, help="enable neo4j tests")


def pytest_configure(config):
    markexpr = getattr(config.option, "markexpr", "")

    if not markexpr:
        markexpr = "not neo4j"
    else:
        markexpr = f"not neo4j and ({markexpr})"

    if not config.option.neo4j:
        setattr(config.option, "markexpr", markexpr)


@pytest.fixture(scope="session", autouse=True)
def add_tracker():
    os.environ["PYTEST_RUNNING"] = "true"


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db(
    neo4j: Optional[dict[int, int]], memgraph: Optional[dict[int, int]], reload_settings_before_each_module
) -> AsyncGenerator[InfrahubDatabase, None]:
    if INFRAHUB_USE_TEST_CONTAINERS:
        config.SETTINGS.database.address = "localhost"
        if neo4j is not None:
            config.SETTINGS.database.port = neo4j[PORT_BOLT_NEO4J]
        else:
            assert memgraph is not None
            config.SETTINGS.database.port = memgraph[PORT_MEMGRAPH]

    driver = InfrahubDatabase(driver=await get_db(retry=5))

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
async def default_ipnamespace(db: InfrahubDatabase, register_core_models_schema) -> Optional[Node]:
    if not registry._default_ipnamespace:
        ip_namespace = await create_ipam_namespace(db=db)
        registry.default_ipnamespace = ip_namespace.id
        return ip_namespace
    return None


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


@pytest.fixture(scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


@pytest.fixture(scope="session")
def prefect_test(prefect_test_fixture):
    with disable_run_logger():
        yield


def get_exposed_port(container: DockerContainer, port: int) -> int:
    """
    Use this method instead of DockerContainer.get_exposed_port as it is decorated with wait_container_is_ready
    which we do not want to use as it does not perform a real healthcheck. DockerContainer.get_exposed_port
    also introduces extra "Waiting for container" logs as we might call it multiple times for containers exposing
    multiple ports such as rabbitmq.
    """

    return int(container.get_docker_client().port(container.get_wrapped_container().id, port))


@pytest.fixture(scope="session")
def neo4j(request: pytest.FixtureRequest, load_settings_before_session) -> Optional[dict[int, int]]:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.database.db_type == "memgraph":
        return None

    container = (
        DockerContainer(image=os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:5.20.0-enterprise"))
        .with_env("NEO4J_AUTH", "neo4j/admin")
        .with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        .with_env("NEO4J_dbms_security_procedures_unrestricted", "apoc.*")
        .with_env("NEO4J_dbms_security_auth__minimum__password__length", "4")
        .with_exposed_ports(PORT_BOLT_NEO4J)
    )

    def cleanup():
        container.stop()

    container.start()
    wait_for_logs(container, "Started.")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(cleanup)

    return {PORT_BOLT_NEO4J: get_exposed_port(container, PORT_BOLT_NEO4J)}


@pytest.fixture(scope="session")
def rabbitmq(request: pytest.FixtureRequest, load_settings_before_session) -> Optional[dict[int, int]]:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.cache.driver == config.CacheDriver.NATS:
        return None

    container = (
        DockerContainer(image="rabbitmq:3.13.1-management")
        .with_env("RABBITMQ_DEFAULT_USER", "infrahub")
        .with_env("RABBITMQ_DEFAULT_PASS", "infrahub")
        .with_exposed_ports(PORT_CLIENT_RABBITMQ, PORT_HTTP_RABBITMQ)
    )

    def cleanup():
        container.stop()

    container.start()
    wait_for_logs(container, "Server startup complete;")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(cleanup)

    return {
        PORT_CLIENT_RABBITMQ: get_exposed_port(container, PORT_CLIENT_RABBITMQ),
        PORT_HTTP_RABBITMQ: get_exposed_port(container, PORT_HTTP_RABBITMQ),
    }


# NOTE: This fixture needs to run before initialize_lock_fixture which is guaranteed to run after as it has a module scope.
@pytest.fixture(scope="session")
def redis(request: pytest.FixtureRequest, load_settings_before_session) -> Optional[dict[int, int]]:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.cache.driver == config.CacheDriver.NATS:
        return None

    container = DockerContainer(image="redis:latest").with_exposed_ports(PORT_REDIS)

    def cleanup():
        container.stop()

    container.start()
    wait_for_logs(container, "Ready to accept connections tcp")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(cleanup)

    return {PORT_REDIS: get_exposed_port(container, PORT_REDIS)}


def wait_for_memgraph_ready(host, port, timeout=15):
    # Not retrieving host/port from config.SETTINGS here as they are set later in `db`fixture.
    URI = f"{config.SETTINGS.database.protocol}://{host}:{port}"

    start_time = time.time()

    with GraphDatabase.driver(URI) as client:
        while time.time() - start_time < timeout:
            try:
                client.verify_connectivity()
                return True
            except ServiceUnavailable:
                time.sleep(1)

    raise TimeoutError(f"memgraph took more than {timeout} seconds to start.")


@pytest.fixture(scope="session")
def memgraph(request: pytest.FixtureRequest, load_settings_before_session) -> Optional[dict[int, int]]:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.database.db_type != "memgraph":
        return None

    memgraph_image = os.getenv("MEMGRAPH_DOCKER_IMAGE", "memgraph/memgraph-mage:1.19-memgraph-2.19-no-ml")

    container = (
        DockerContainer(image=memgraph_image, init=True)
        .with_env("APP_CYPHER_QUERY_MAX_LEN", 10000)
        .with_exposed_ports(PORT_MEMGRAPH)
    )

    def cleanup():
        container.stop()

    container.start()

    # Waiting for logs is not enough to make sure memgraph is available.
    # Here we need to use DockerContainer.get_exposed_port instead of our own get_exposed_port
    # in order to wait for the port to be exposed. This call is responsible for "Waiting for memgraph to be ready" logs.
    # Note we still need to call wait_for_memgraph_ready to be sure the container is fully started.
    wait_for_memgraph_ready(host="localhost", port=container.get_exposed_port(PORT_MEMGRAPH))

    request.addfinalizer(cleanup)

    return {PORT_MEMGRAPH: get_exposed_port(container, PORT_MEMGRAPH)}


@pytest.fixture(scope="session")
def nats(request: pytest.FixtureRequest, load_settings_before_session) -> Optional[dict[int, int]]:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        return None

    container = DockerContainer(image="nats:alpine").with_command("--jetstream").with_exposed_ports(PORT_NATS)

    def cleanup():
        container.stop()

    container.start()
    wait_for_logs(container, "Server is ready")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(cleanup)

    return {PORT_NATS: get_exposed_port(container, PORT_NATS)}


@pytest.fixture(scope="session", autouse=True)
def load_settings_before_session():
    load_and_exit()


@pytest.fixture(scope="module", autouse=True)
def reload_settings_before_each_module(
    tmpdir_factory,
    redis: Optional[dict[int, int]],
    rabbitmq: Optional[dict[int, int]],
    nats: Optional[dict[int, int]],
):
    # Currently, tests assume cache and broker are always up, thus fixtures are always called even for tests not requiring them.
    # An improvement would be to have cache and broker fixtures used only for tests which actually need them, as we do with 'db' fixture.
    # Also note that later call to initialize_lock requires redis fixture.

    # Settings need to be reloaded between each test module, as some module might modify settings that might break tests within other modules.
    load_and_exit()

    if INFRAHUB_USE_TEST_CONTAINERS:
        # Cache settings: either Redis or Nats.
        config.SETTINGS.cache.address = "localhost"
        if redis is not None:
            config.SETTINGS.cache.port = redis[PORT_REDIS]
        else:
            assert nats is not None
            config.SETTINGS.cache.port = nats[PORT_NATS]

        # Broker settings: either RabbitMQ or Nats.
        config.SETTINGS.broker.address = "localhost"
        if rabbitmq is not None:
            config.SETTINGS.broker.port = rabbitmq[PORT_CLIENT_RABBITMQ]
            config.SETTINGS.broker.rabbitmq_http_port = rabbitmq[PORT_HTTP_RABBITMQ]
        else:
            assert nats is not None
            config.SETTINGS.broker.port = nats[PORT_NATS]

    # Other settings
    config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage

    storage_dir = tmpdir_factory.mktemp("storage")
    config.SETTINGS.storage.local.path_ = str(storage_dir)

    config.SETTINGS.broker.enable = False
    config.SETTINGS.cache.enable = True
    config.SETTINGS.miscellaneous.start_background_runner = False
    config.SETTINGS.security.secret_key = "4e26b3d9-b84f-42c9-a03f-fee3ada3b2fa"
    config.SETTINGS.main.internal_address = "http://mock"
    config.OVERRIDE.message_bus = BusRecorder()

    initialize_lock()


@pytest.fixture
async def data_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    SCHEMA: dict[str, Any] = {
        "generics": [
            {
                "name": "Owner",
                "namespace": "Lineage",
            },
            {
                "name": "Source",
                "description": "Any Entities that stores or produces data.",
                "namespace": "Lineage",
            },
            core_profile_schema_definition,
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def group_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA: dict[str, Any] = {
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
async def car_person_schema_unregistered(db: InfrahubDatabase, node_group_schema, data_schema) -> SchemaRoot:
    schema: dict[str, Any] = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "uniqueness_constraints": [["name__value"]],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number", "optional": True},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7, "optional": True},
                    {"name": "is_electric", "kind": "Boolean", "optional": True},
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
                        "label": "Commander of Car",
                        "peer": "TestPerson",
                        "optional": False,
                        "kind": "Parent",
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
                "uniqueness_constraints": [["name__value"]],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many", "direction": "inbound"}],
            },
        ],
    }

    return SchemaRoot(**schema)


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered
) -> SchemaBranch:
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def animal_person_schema_unregistered(db: InfrahubDatabase, node_group_schema, data_schema) -> SchemaRoot:
    schema: dict[str, Any] = {
        "generics": [
            {
                "name": "Animal",
                "namespace": "Test",
                "human_friendly_id": ["owner__name__value", "name__value"],
                "uniqueness_constraints": [
                    ["owner", "name__value"],
                ],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "weight", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "optional": False,
                        "identifier": "person__animal",
                        "cardinality": "one",
                        "direction": "outbound",
                    },
                    {
                        "name": "best_friend",
                        "peer": "TestPerson",
                        "optional": True,
                        "identifier": "person__animal_friend",
                        "cardinality": "one",
                        "direction": "outbound",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Dog",
                "namespace": "Test",
                "inherit_from": ["TestAnimal"],
                "display_labels": ["name__value", "breed__value"],
                "attributes": [
                    {"name": "breed", "kind": "Text", "optional": False},
                    {"name": "color", "kind": "Color", "default_value": "#444444", "optional": True},
                ],
            },
            {
                "name": "Cat",
                "namespace": "Test",
                "inherit_from": ["TestAnimal"],
                "display_labels": ["name__value", "breed__value", "color__value"],
                "attributes": [
                    {"name": "breed", "kind": "Text", "optional": False},
                    {"name": "color", "kind": "Color", "default_value": "#444444", "optional": True},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "default_filter": "name__value",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "animals",
                        "peer": "TestAnimal",
                        "identifier": "person__animal",
                        "cardinality": "many",
                        "direction": "inbound",
                    },
                    {
                        "name": "best_friends",
                        "peer": "TestAnimal",
                        "identifier": "person__animal_friend",
                        "cardinality": "many",
                        "direction": "inbound",
                    },
                ],
            },
        ],
    }

    return SchemaRoot(**schema)


@pytest.fixture
async def animal_person_schema(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema_unregistered
) -> SchemaBranch:
    return registry.schema.register_schema(schema=animal_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def node_group_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA: dict[str, Any] = {
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
                "uniqueness_constraints": [["name__value"]],
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


@pytest.fixture(scope="module")
def tmp_path_module_scope() -> Generator[Path, None, None]:
    """Fixture similar to tmp_path but with scope=module"""
    with TemporaryDirectory() as tmpdir:
        directory = tmpdir
        if sys.platform == "darwin" and tmpdir.startswith("/var/"):
            # On Mac /var is symlinked to /private/var. TemporaryDirectory uses the /var prefix
            # however when using 'git worktree list --porcelain' the path is returned with
            # /prefix/var and InfrahubRepository fails to initialize the repository as the
            # relative path of the repository isn't handled correctly
            directory = f"/private{tmpdir}"
        yield Path(directory)


@pytest.fixture(scope="module")
def git_repos_dir_module_scope(tmp_path_module_scope: Path) -> Generator[Path, None, None]:
    repos_dir = tmp_path_module_scope / "repositories"
    repos_dir.mkdir()

    old_repos_dir = config.SETTINGS.git.repositories_directory
    config.SETTINGS.git.repositories_directory = str(repos_dir)

    yield repos_dir

    config.SETTINGS.git.repositories_directory = old_repos_dir


@pytest.fixture(scope="module")
def git_repos_source_dir_module_scope(tmp_path_module_scope: Path) -> Path:
    repos_dir = tmp_path_module_scope / "source"
    repos_dir.mkdir()
    return repos_dir


class BusRPCMock(InfrahubMessageBus):
    def __init__(self) -> None:
        self.response: list[InfrahubResponse] = []
        self.messages: list[InfrahubMessage] = []

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None, is_retry: bool = False
    ) -> None:
        self.messages.append(message)

    def add_mock_reply(self, response: InfrahubResponse):
        self.response.append(response)

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        self.messages.append(message)
        response = self.response.pop()
        data = ujson.loads(response.body)
        return response_class(**data)


class TestHelper:
    """TestHelper profiles functions that can be used as a fixture throughout the test framework"""

    @staticmethod
    def schema_file(file_name: str) -> dict:
        """Return the contents of a schema file as a dictionary"""
        file_content = Path(os.path.join(TestHelper.get_fixtures_dir(), f"schemas/{file_name}")).read_text(
            encoding="utf-8"
        )

        return ujson.loads(file_content)

    @staticmethod
    def get_fixtures_dir() -> Path:
        """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
        here = Path(__file__).parent.resolve()
        return here / "fixtures"

    @staticmethod
    def import_module_in_fixtures(module: str) -> Any:
        """Import a python module from the fixtures directory."""

        sys.path.append(str(TestHelper.get_fixtures_dir()))
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


@pytest.fixture()
def fake_log() -> FakeLogger:
    return FakeLogger()


@pytest.fixture()
def helper() -> TestHelper:
    return TestHelper()


@pytest.fixture
def patch_services(helper):
    original = services.service.message_bus
    bus = helper.get_message_bus_rpc()
    services.service.message_bus = bus
    services.prepare(service=services.service)
    yield bus
    services.service.message_bus = original
    services.prepare(service=services.service)
