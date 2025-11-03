import asyncio
import importlib
import logging
import os
import sys
import time
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, AsyncGenerator, Generator, TypeVar

import pytest
import ujson
from fast_depends import Provider
from fast_depends import dependency_provider as provider
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from prefect import settings as prefect_settings
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub import config
from infrahub.config import load_and_exit
from infrahub.constants.database import Neo4jRuntime
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind, RelationshipCardinality, RelationshipDirection
from infrahub.core.initialization import (
    add_indexes,
    create_branch,
    create_default_branch,
    create_global_branch,
    create_ipam_namespace,
    create_root_node,
)
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.lock import initialize_lock
from infrahub.message_bus import InfrahubMessage, InfrahubResponse
from infrahub.message_bus.types import MessageTTL
from infrahub.permissions import LocalPermissionBackend
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from tests.adapters.log import FakeLogger
from tests.adapters.message_bus import BusRecorder, BusSimulator
from tests.helpers.constants import (
    INFRAHUB_USE_TEST_CONTAINERS,
    NEO4J_IMAGE,
    PORT_BOLT_NEO4J,
    PORT_CLIENT_RABBITMQ,
    PORT_HTTP_NEO4J,
    PORT_HTTP_RABBITMQ,
    PORT_MEMGRAPH,
    PORT_NATS,
    PORT_PREFECT,
    PORT_REDIS,
)
from tests.helpers.utils import get_exposed_port, start_neo4j_container, start_prefect_server_container

ResponseClass = TypeVar("ResponseClass")
DEFAULT_TESTING_LOG_LEVEL = "WARNING"

pytest.register_assert_rewrite("tests.db_snapshot")

graphql_registry.clear_cache()


def pytest_addoption(parser) -> None:
    parser.addoption("--neo4j", action="store_true", dest="neo4j", default=False, help="enable neo4j tests")


def pytest_configure(config) -> None:
    markexpr = getattr(config.option, "markexpr", "")

    if not markexpr:
        markexpr = "not neo4j"
    else:
        markexpr = f"not neo4j and ({markexpr})"

    if not config.option.neo4j:
        config.option.markexpr = markexpr

    log_level = config.option.log_level
    log_level = log_level if log_level is not None else DEFAULT_TESTING_LOG_LEVEL

    # We can't control logging through INFRAHUB_LOG_LEVEL and PREFECT_LOGGING_LEVEL here
    # because logging configuration has already been setup when `log.py` is imported,
    # thus we directly set level of corresponding loggers.
    logging.getLogger().setLevel(log_level)  # root logger
    logging.getLogger("prefect").setLevel(log_level)  # prefect logger


@pytest.fixture(scope="session", autouse=True)
def add_tracker() -> None:
    os.environ["PYTEST_RUNNING"] = "true"


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def dependency_provider() -> Provider:
    return provider


@pytest.fixture(scope="module")
async def db(
    neo4j: dict[int, int] | None, memgraph: dict[int, int] | None, reload_settings_before_each_module
) -> AsyncGenerator[InfrahubDatabase, None]:
    if INFRAHUB_USE_TEST_CONTAINERS:
        config.SETTINGS.database.address = "localhost"
        if neo4j is not None:
            config.SETTINGS.database.port = neo4j[PORT_BOLT_NEO4J]
        else:
            assert memgraph is not None
            config.SETTINGS.database.port = memgraph[PORT_MEMGRAPH]

    driver = InfrahubDatabase(driver=await get_db(retry=5))
    await add_indexes(db=driver)

    yield driver

    await driver.close()


@pytest.fixture
async def empty_database(db: InfrahubDatabase) -> None:
    await do_empty_database(db=db)


async def do_empty_database(db: InfrahubDatabase) -> None:
    await delete_all_nodes(db=db)
    await create_root_node(db=db)


@pytest.fixture
async def reset_registry(db: InfrahubDatabase) -> None:
    await do_reset_registry(db=db)


async def do_reset_registry(db: InfrahubDatabase) -> None:
    registry.delete_all()


@pytest.fixture
async def default_branch(reset_registry, local_storage_dir, empty_database, db: InfrahubDatabase) -> Branch:
    return await do_default_branch(db=db)


async def do_default_branch(db: InfrahubDatabase) -> Branch:
    branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()
    return branch


@pytest.fixture
def query_limit_of_one() -> Generator[None, None, None]:
    original_query_size_limit = config.SETTINGS.database.query_size_limit
    config.SETTINGS.database.query_size_limit = 1
    yield
    config.SETTINGS.database.query_size_limit = original_query_size_limit


@pytest.fixture
def neo4j_runtime_parallel(db: InfrahubDatabase) -> Generator[None, None, None]:
    original_neo4j_runtime = db.default_neo4j_runtime
    db.default_neo4j_runtime = Neo4jRuntime.PARALLEL
    yield
    db.default_neo4j_runtime = original_neo4j_runtime


@pytest.fixture
async def default_ipnamespace(db: InfrahubDatabase, register_core_models_schema) -> Node | None:
    if not registry._default_ipnamespace:
        ip_namespace = await create_ipam_namespace(db=db)
        registry.default_ipnamespace = ip_namespace.id
        return ip_namespace
    return None


@pytest.fixture
def default_permission_backend() -> Generator[None, Any, Any]:
    previous_backends = registry.permission_backends
    registry.permission_backends = [LocalPermissionBackend()]
    yield
    registry.permission_backends = previous_backends


@pytest.fixture
def local_storage_dir(tmp_path: Path) -> Path:
    return do_local_storage_dir(tmp_path=tmp_path)


def do_local_storage_dir(tmp_path: Path) -> Path:
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
    config.SETTINGS.storage.local.path_ = storage_dir

    return storage_dir


@pytest.fixture
async def register_internal_models_schema(default_branch: Branch) -> SchemaBranch:
    return await do_register_internal_models_schema(branch=default_branch)


async def do_register_internal_models_schema(branch: Branch) -> SchemaBranch:
    schema = SchemaRoot(**internal_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=branch.name)
    branch.update_schema_hash()
    return schema_branch


@pytest.fixture
async def register_core_models_schema(default_branch: Branch, register_internal_models_schema) -> SchemaBranch:
    return await do_register_core_models_schema(branch=default_branch)


async def do_register_core_models_schema(branch: Branch) -> SchemaBranch:
    schema = SchemaRoot(**core_models)
    schema_branch = registry.schema.register_schema(schema=schema, branch=branch.name)
    branch.update_schema_hash()
    return schema_branch


@pytest.fixture(scope="session")
def neo4j(request: pytest.FixtureRequest, load_settings_before_session) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.database.db_type == "memgraph":
        return None

    container = start_neo4j_container(NEO4J_IMAGE)
    request.addfinalizer(container.stop)

    return {
        PORT_BOLT_NEO4J: get_exposed_port(container, PORT_BOLT_NEO4J),
        PORT_HTTP_NEO4J: get_exposed_port(container, PORT_HTTP_NEO4J),
    }


@pytest.fixture(scope="session")
def rabbitmq_container(request: pytest.FixtureRequest, load_settings_before_session) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.broker.driver != config.BrokerDriver.RabbitMQ:
        return None

    container = (
        DockerContainer(image="rabbitmq:3.13.1-management")
        .with_env("RABBITMQ_DEFAULT_USER", "infrahub")
        .with_env("RABBITMQ_DEFAULT_PASS", "infrahub")
        .with_exposed_ports(PORT_CLIENT_RABBITMQ, PORT_HTTP_RABBITMQ)
    )

    container.start()
    wait_for_logs(container, "Server startup complete;")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(container.stop)

    return {
        PORT_CLIENT_RABBITMQ: get_exposed_port(container, PORT_CLIENT_RABBITMQ),
        PORT_HTTP_RABBITMQ: get_exposed_port(container, PORT_HTTP_RABBITMQ),
    }


@pytest.fixture(scope="module")
def rabbitmq(rabbitmq_container: dict[int, int] | None, reload_settings_before_each_module) -> dict[int, int] | None:
    if (
        rabbitmq_container
        and INFRAHUB_USE_TEST_CONTAINERS
        and config.SETTINGS.broker.driver == config.BrokerDriver.RabbitMQ
    ):
        config.SETTINGS.broker.address = "localhost"
        config.SETTINGS.broker.port = rabbitmq_container[PORT_CLIENT_RABBITMQ]
        config.SETTINGS.broker.rabbitmq_http_port = rabbitmq_container[PORT_HTTP_RABBITMQ]
        return rabbitmq_container

    return None


# NOTE: This fixture needs to run before initialize_lock_fixture which is guaranteed to run after as it has a module scope.
@pytest.fixture(scope="session")
def redis_container(request: pytest.FixtureRequest, load_settings_before_session) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        return None

    container = DockerContainer(image="redis:7.2.11").with_exposed_ports(PORT_REDIS)

    container.start()
    wait_for_logs(container, "Ready to accept connections tcp")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(container.stop)

    return {PORT_REDIS: get_exposed_port(container, PORT_REDIS)}


@pytest.fixture(scope="module")
def redis(redis_container: dict[int, int] | None, reload_settings_before_each_module) -> dict[int, int] | None:
    if redis_container and INFRAHUB_USE_TEST_CONTAINERS and config.SETTINGS.cache.driver == config.CacheDriver.Redis:
        config.SETTINGS.cache.address = "localhost"
        config.SETTINGS.cache.port = redis_container[PORT_REDIS]
        config.SETTINGS.cache.username = ""
        config.SETTINGS.cache.password = ""

        return redis_container

    return None


def wait_for_memgraph_ready(host, port, timeout=15) -> bool:
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
def memgraph(request: pytest.FixtureRequest, load_settings_before_session) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.database.db_type != "memgraph":
        return None

    memgraph_image = os.getenv("MEMGRAPH_DOCKER_IMAGE", "memgraph/memgraph-mage:1.19-memgraph-2.19-no-ml")

    container = (
        DockerContainer(image=memgraph_image, init=True)
        .with_env("APP_CYPHER_QUERY_MAX_LEN", 10000)
        .with_exposed_ports(PORT_MEMGRAPH)
    )

    container.start()

    # Waiting for logs is not enough to make sure memgraph is available.
    # Here we need to use DockerContainer.get_exposed_port instead of our own get_exposed_port
    # in order to wait for the port to be exposed. This call is responsible for "Waiting for memgraph to be ready" logs.
    # Note we still need to call wait_for_memgraph_ready to be sure the container is fully started.
    wait_for_memgraph_ready(host="localhost", port=container.get_exposed_port(PORT_MEMGRAPH))

    request.addfinalizer(container.stop)

    return {PORT_MEMGRAPH: get_exposed_port(container, PORT_MEMGRAPH)}


@pytest.fixture(scope="session")
def nats_container(request: pytest.FixtureRequest, load_settings_before_session) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS or config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        return None

    container = DockerContainer(image="nats:alpine").with_command("--jetstream").with_exposed_ports(PORT_NATS)

    container.start()
    wait_for_logs(container, "Server is ready")  # wait_container_is_ready does not seem to be enough
    request.addfinalizer(container.stop)

    return {PORT_NATS: get_exposed_port(container, PORT_NATS)}


@pytest.fixture(scope="module")
def nats(nats_container: dict[int, int] | None, reload_settings_before_each_module) -> dict[int, int] | None:
    if nats_container and INFRAHUB_USE_TEST_CONTAINERS and config.SETTINGS.cache.driver == config.CacheDriver.NATS:
        config.SETTINGS.cache.address = "localhost"
        config.SETTINGS.cache.port = nats_container[PORT_NATS]

    if nats_container and INFRAHUB_USE_TEST_CONTAINERS and config.SETTINGS.broker.driver == config.BrokerDriver.NATS:
        config.SETTINGS.broker.address = "localhost"
        config.SETTINGS.broker.port = nats_container[PORT_NATS]

        return nats_container

    return None


@pytest.fixture(scope="session")
def prefect_container(request: pytest.FixtureRequest, load_settings_before_session) -> dict[int, int] | None:
    return start_prefect_server_container(request)


@pytest.fixture(scope="module")
def prefect(prefect_container: dict[int, int] | None, reload_settings_before_each_module) -> Generator[str, None, None]:
    if prefect_container:
        server_port = prefect_container[PORT_PREFECT]
        server_api_url = f"http://localhost:{server_port}/api"
    else:
        server_api_url = f"http://localhost:{PORT_PREFECT}/api"

    with ExitStack() as stack:
        stack.enter_context(
            prefect_settings.temporary_settings(
                updates={
                    prefect_settings.PREFECT_API_URL: server_api_url,
                }
            )
        )
        yield server_api_url


@pytest.fixture(scope="session", autouse=True)
def load_settings_before_session() -> None:
    load_and_exit()


@pytest.fixture(scope="module", autouse=True)
def reload_settings_before_each_module(tmpdir_factory) -> None:
    # Settings need to be reloaded between each test module, as some module might modify settings that might break tests within other modules.
    load_and_exit()

    # Other settings
    config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
    config.SETTINGS.workflow.driver = config.WorkflowDriver.LOCAL

    storage_dir = tmpdir_factory.mktemp("storage")
    config.SETTINGS.storage.local.path_ = storage_dir

    config.SETTINGS.broker.enable = False
    config.SETTINGS.cache.enable = True
    config.SETTINGS.miscellaneous.start_background_runner = False
    config.SETTINGS.security.secret_key = "4e26b3d9-b84f-42c9-a03f-fee3ada3b2fa"
    config.SETTINGS.main.internal_address = "http://mock"
    config.OVERRIDE.message_bus = BusRecorder()

    initialize_lock(local_only=True)


@pytest.fixture
def enable_broker_config():
    # This is required for situations where we need the broker to be enabled.
    # We should really remove this setting as it doesn't make any sense to have
    # outside of the test environment
    original_config = config.SETTINGS.broker.enable
    config.SETTINGS.broker.enable = True
    yield
    config.SETTINGS.broker.enable = original_config


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
                    {
                        "name": "driver",
                        "label": "Commander of Car",
                        "peer": "TestPerson",
                        "optional": True,
                        "cardinality": "one",
                        "identifier": "cars_driven__driver",
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
                "relationships": [
                    {"name": "cars", "peer": "TestCar", "cardinality": "many", "direction": "inbound"},
                    {
                        "name": "cars_driven",
                        "peer": "TestCar",
                        "cardinality": "many",
                        "identifier": "cars_driven__driver",
                    },
                ],
            },
        ],
    }

    return SchemaRoot(**schema)


@pytest.fixture
async def person_schema_default_filter(db: InfrahubDatabase, node_group_schema, data_schema) -> SchemaRoot:
    """
    Person schema with no unicity constraint set except default filter.
    """

    schema: dict[str, Any] = {
        "nodes": [
            {
                "name": "PersonDF",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
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
async def car_person_schema_branch_local_root(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Car",
                namespace="Test",
                default_filter="name__value",
                display_labels=["name__value", "color__value"],
                uniqueness_constraints=[["name__value"]],
                branch=BranchSupportType.LOCAL,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="color", kind="Text", default_value="#444444", optional=True),
                ],
                relationships=[
                    RelationshipSchema(
                        name="owner",
                        peer="TestPerson",
                        optional=False,
                        cardinality=RelationshipCardinality.ONE,
                        direction=RelationshipDirection.OUTBOUND,
                    ),
                ],
            ),
            NodeSchema(
                name="Person",
                namespace="Test",
                default_filter="name__value",
                display_labels=["name__value"],
                branch=BranchSupportType.AWARE,
                uniqueness_constraints=[["name__value"]],
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="height", kind="Number", optional=True),
                ],
                relationships=[
                    RelationshipSchema(
                        name="cars",
                        peer="TestCar",
                        cardinality=RelationshipCardinality.MANY,
                        direction=RelationshipDirection.INBOUND,
                    )
                ],
            ),
        ],
    )
    return schema


@pytest.fixture
async def car_person_schema_branch_local(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_branch_local_root
) -> SchemaBranch:
    return registry.schema.register_schema(schema=car_person_schema_branch_local_root, branch=default_branch.name)


@pytest.fixture
async def animal_person_schema_unregistered(db: InfrahubDatabase, node_group_schema, data_schema) -> dict:
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

    return schema


@pytest.fixture
async def animal_person_schema_person_no_default_filter(
    db: InfrahubDatabase, default_branch, node_group_schema, data_schema, animal_person_schema_unregistered
) -> SchemaBranch:
    schema_dict = deepcopy(animal_person_schema_unregistered)
    del schema_dict["nodes"][2]["default_filter"]
    return registry.schema.register_schema(schema=SchemaRoot(**schema_dict), branch=default_branch.name)


@pytest.fixture
async def person_schema_unique_attr_non_hfid_unregistered(
    db: InfrahubDatabase, node_group_schema, data_schema
) -> SchemaRoot:
    schema: dict[str, Any] = {
        "nodes": [
            {
                "name": "Person",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                    {"name": "bag", "kind": "Text", "unique": True},
                ],
            },
            {
                "name": "Car",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "human_friendly_id": ["owner__name__value", "name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "color", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {"name": "owner", "peer": "TestPerson", "cardinality": "one", "optional": False},
                    {
                        "name": "things",
                        "peer": "TestThing",
                        "cardinality": "many",
                        "optional": True,
                        "identifier": "carthings",
                    },
                ],
            },
            {
                "name": "Thing",
                "namespace": "Test",
                "display_labels": ["value__value"],
                "attributes": [
                    {"name": "value", "kind": "Text"},
                ],
                "relationships": [
                    {
                        "name": "car",
                        "peer": "TestCar",
                        "cardinality": "one",
                        "optional": True,
                        "identifier": "carthings",
                    }
                ],
            },
        ],
    }

    return SchemaRoot(**schema)


@pytest.fixture
async def person_schema_unique_attr_non_hfid(
    db: InfrahubDatabase, default_branch: Branch, person_schema_unique_attr_non_hfid_unregistered
) -> SchemaBranch:
    return registry.schema.register_schema(
        schema=person_schema_unique_attr_non_hfid_unregistered, branch=default_branch.name
    )


@pytest.fixture
async def animal_person_schema(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema_unregistered
) -> SchemaBranch:
    schema_root = SchemaRoot(**animal_person_schema_unregistered)
    return registry.schema.register_schema(schema=schema_root, branch=default_branch.name)


@pytest.fixture
async def dependent_generics_unregistered(db: InfrahubDatabase, node_group_schema, data_schema) -> SchemaRoot:
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
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "human_friendly_id": ["name__value"],
                "uniqueness_constraints": [
                    ["name__value"],
                ],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text"},
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
                "name": "Human",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "inherit_from": ["TestPerson"],
                "human_friendly_id": ["name__value"],
            },
            {
                "name": "Cylon",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "inherit_from": ["TestPerson"],
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "model_number", "kind": "Number", "optional": False},
                ],
            },
        ],
    }

    return SchemaRoot(**schema)


@pytest.fixture
async def dependent_generics_schema(
    db: InfrahubDatabase, default_branch: Branch, dependent_generics_unregistered
) -> SchemaBranch:
    return registry.schema.register_schema(schema=dependent_generics_unregistered, branch=default_branch.name)


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


@pytest.fixture
async def standard_group_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "StandardGroup",
                "namespace": "Core",
                "inherit_from": [InfrahubKind.GENERICGROUP],
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            }
        ]
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
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        self.messages.append(message)

    def add_mock_reply(self, response: InfrahubResponse) -> None:
        self.response.append(response)

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        self.messages.append(message)
        response = self.response.pop()
        data = ujson.loads(response.body)
        return response_class(**data)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise ValueError("BusRPCMock.reply should not be called")


class TestHelper:
    """TestHelper profiles functions that can be used as a fixture throughout the test framework"""

    @staticmethod
    def schema_file(file_name: str) -> dict:
        """Return the contents of a schema file as a dictionary"""
        file_content = (TestHelper.get_fixtures_dir() / "schemas" / file_name).read_text(encoding="utf-8")

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
    async def get_message_bus_simulator(db: InfrahubDatabase | None = None) -> BusSimulator:
        service = await InfrahubServices.new(database=db, message_bus=BusSimulator())
        message_bus = service.message_bus
        assert isinstance(message_bus, BusSimulator)
        return message_bus

    @staticmethod
    def get_message_bus_rpc() -> BusRPCMock:
        return BusRPCMock()


@pytest.fixture
def fake_log() -> FakeLogger:
    return FakeLogger()


@pytest.fixture
def helper() -> TestHelper:
    return TestHelper()


@pytest.fixture(scope="class")
def car_person_branch_agnostic_schema() -> dict[str, Any]:
    schema: dict[str, Any] = {
        "version": "1.0",
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "uniqueness_constraints": [["agnostic_owner"]],
                "human_friendly_id": ["name__value"],
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "agnostic_owner",
                        "label": "Commander of Car",
                        "peer": "TestPerson",
                        "optional": False,
                        "cardinality": "one",
                        "direction": "outbound",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "identifier": "agnostic_owner",
                    },
                    {
                        "name": "aware_owner",
                        "label": "Commander of Car",
                        "peer": "TestPerson",
                        "optional": True,
                        "cardinality": "one",
                        "direction": "outbound",
                        "branch": BranchSupportType.AWARE.value,
                        "identifier": "aware_owner",
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
                ],
                "relationships": [
                    {
                        "name": "cars",
                        "peer": "TestCar",
                        "cardinality": "many",
                        "direction": "inbound",
                        "branch": BranchSupportType.AGNOSTIC.value,
                    }
                ],
            },
            {
                "name": "Roofrack",
                "namespace": "Test",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "size", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "car",
                        "label": "Commander of Car",
                        "peer": "TestCar",
                        "optional": False,
                        "kind": "Parent",
                        "cardinality": "one",
                        "direction": "outbound",
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                ],
            },
        ],
    }
    return schema


@pytest.fixture
async def car_person_schema_unique_owner(db: InfrahubDatabase, node_group_schema, data_schema) -> dict:
    schema: dict[str, Any] = {
        "version": "1.0",
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "uniqueness_constraints": [["name__value"], ["owner"]],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number", "optional": True},
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

    return schema


@pytest.fixture(params=["main", "branch2"])
async def branch(request, db: InfrahubDatabase, default_branch: Branch):
    if request.param == "main":
        return default_branch

    return await create_branch(branch_name=str(request.param), db=db)


@pytest.fixture
async def schemas_conversion(db: InfrahubDatabase, node_group_schema, data_schema) -> dict:
    schema: dict[str, Any] = {
        "version": "1.0",
        "generics": [
            {
                "name": "PersonGeneric",
                "namespace": "Testconv",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                    {"name": "favorite_color", "kind": "Text", "optional": True, "default_value": "blue"},
                ],
                "relationships": [
                    {
                        "name": "favorite_car",
                        "peer": "TestconvCar",
                        "cardinality": "one",
                        "identifier": "person__favorite_car",
                    },
                    {
                        "name": "fastest_cars",
                        "peer": "TestconvCar",
                        "cardinality": "many",
                        "identifier": "person__fastest_cars",
                    },
                    {
                        "name": "bags",
                        "peer": "TestconvBag",
                        "cardinality": "many",
                        "identifier": "person__bag",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Person1",
                "namespace": "Testconv",
                "inherit_from": ["TestconvPersonGeneric"],
                "relationships": [],
            },
            {
                "name": "Person2",
                "namespace": "Testconv",
                "inherit_from": ["TestconvPersonGeneric"],
                "attributes": [
                    {"name": "age", "kind": "Number"},
                    {"name": "citizenship", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "worst_car",
                        "peer": "TestconvCar",
                        "cardinality": "one",
                        "identifier": "person__worst_car",
                    },
                    {
                        "name": "slowest_cars",
                        "peer": "TestconvCar",
                        "cardinality": "many",
                        "optional": True,
                        "identifier": "person__slowest_cars",
                    },
                ],
            },
            {
                "name": "Car",
                "namespace": "Testconv",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestconvPersonGeneric",
                        "cardinality": "one",
                        "identifier": "person__fastest_cars",
                        "optional": True,
                    },
                ],
            },
            {
                "name": "Bag",
                "namespace": "Testconv",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestconvPersonGeneric",
                        "cardinality": "one",
                        "identifier": "person__bag",
                        "optional": False,
                    },
                ],
            },
        ],
    }

    return schema


@pytest.fixture
async def schema_conversion_mandatory_owner(db: InfrahubDatabase, node_group_schema, data_schema) -> dict:
    schema: dict[str, Any] = {
        "version": "1.0",
        "generics": [
            {
                "name": "PersonGeneric",
                "namespace": "Testmo",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "my_car",
                        "peer": "TestmoCar",
                        "cardinality": "one",
                        "identifier": "person__mandatory_owner",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Person1",
                "namespace": "Testmo",
                "inherit_from": ["TestmoPersonGeneric"],
            },
            {
                "name": "Person2",
                "namespace": "Testmo",
                "inherit_from": ["TestmoPersonGeneric"],
            },
            {
                "name": "Car",
                "namespace": "Testmo",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "mandatory_owner",
                        "peer": "TestmoPersonGeneric",
                        "cardinality": "one",
                        "optional": False,
                        "identifier": "person__mandatory_owner",
                    }
                ],
            },
        ],
    }

    return schema


@pytest.fixture
async def schema_conversion_aware_agnostic(db: InfrahubDatabase, node_group_schema, data_schema) -> dict:
    schema: dict[str, Any] = {
        "version": "1.0",
        "generics": [
            {
                "name": "PersonGeneric",
                "namespace": "Testbs",
                "human_friendly_id": ["name_agnostic__value"],
                "attributes": [
                    {
                        "name": "name_agnostic",
                        "kind": "Text",
                        "unique": True,
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Person1",
                "namespace": "Testbs",
                "inherit_from": ["TestbsPersonGeneric"],
                "attributes": [
                    {
                        "name": "age_1_agnostic",
                        "kind": "Number",
                        "unique": True,
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                    {
                        "name": "height_1_aware",
                        "kind": "Number",
                        "unique": True,
                        "branch": BranchSupportType.AWARE.value,
                    },
                ],
            },
            {
                "name": "Person2",
                "namespace": "Testbs",
                "inherit_from": ["TestbsPersonGeneric"],
                "attributes": [
                    {"name": "age_2_aware", "kind": "Number", "unique": True, "branch": BranchSupportType.AWARE.value},
                    {
                        "name": "height_2_agnostic",
                        "kind": "Number",
                        "unique": True,
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                ],
            },
            {
                "name": "Car",
                "namespace": "Testbs",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
        ],
    }

    return schema


@pytest.fixture
async def schema_conversion_agnostic_node_with_aware_attributes(
    db: InfrahubDatabase, node_group_schema, data_schema
) -> dict:
    schema: dict[str, Any] = {
        "version": "1.0",
        "generics": [
            {
                "name": "PersonGeneric",
                "namespace": "Testaa",
                "human_friendly_id": ["name_agnostic__value"],
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {
                        "name": "name_agnostic",
                        "kind": "Text",
                        "unique": True,
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                    {
                        "name": "age_aware",
                        "kind": "Number",
                        "branch": BranchSupportType.AWARE.value,
                    },
                ],
                "relationships": [
                    {
                        "name": "favorite_car",
                        "peer": "TestaaCar",
                        "cardinality": "one",
                        "optional": True,
                        "identifier": "person__favorite_car",
                    },
                    {
                        "name": "other_cars",
                        "peer": "TestaaCar",
                        "cardinality": "many",
                        "optional": True,
                        "identifier": "person__other_cars",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Person1",
                "namespace": "Testaa",
                "inherit_from": ["TestaaPersonGeneric"],
                "branch": BranchSupportType.AGNOSTIC.value,
            },
            {
                "name": "Person2",
                "namespace": "Testaa",
                "branch": BranchSupportType.AGNOSTIC.value,
                "inherit_from": ["TestaaPersonGeneric"],
                "attributes": [
                    {
                        "name": "height_aware",
                        "kind": "Number",
                        "branch": BranchSupportType.AWARE.value,
                    },
                ],
            },
            {
                "name": "Car",
                "namespace": "Testaa",
                "human_friendly_id": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "favorite_person",
                        "peer": "TestaaPersonGeneric",
                        "cardinality": "one",
                        "optional": True,
                        "identifier": "person__favorite_car",
                    },
                    {
                        "name": "owner",
                        "peer": "TestaaPersonGeneric",
                        "cardinality": "one",
                        "optional": True,
                        "identifier": "person__other_cars",
                    },
                ],
            },
        ],
    }

    return schema


@pytest.fixture
async def schema_conversion_unidirectional_relationships(db: InfrahubDatabase, node_group_schema, data_schema) -> dict:
    schema: dict[str, Any] = {
        "version": "1.0",
        "generics": [
            {
                "name": "PersonGeneric",
                "namespace": "Testud",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {
                        "name": "name",
                        "kind": "Text",
                        "unique": True,
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Person1",
                "namespace": "Testud",
                "inherit_from": ["TestudPersonGeneric"],
            },
            {
                "name": "Person2",
                "namespace": "Testud",
                "inherit_from": ["TestudPersonGeneric"],
            },
            {
                "name": "Car",
                "namespace": "Testud",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "unidirectional_owner",
                        "peer": "TestudPersonGeneric",
                        "cardinality": "one",
                        "optional": False,
                    },
                ],
            },
        ],
    }

    return schema
