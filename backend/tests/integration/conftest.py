import asyncio
import contextlib
import ctypes
import gc
import os
from pathlib import Path
from typing import Any, Generator
from unittest.mock import patch

import pytest
import yaml
from infrahub_sdk.uuidt import UUIDT
from prefect.server.api.server import SubprocessASGIServer
from prefect.testing.utilities import prefect_test_harness
from pytest import TempPathFactory

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.utils import get_models_dir
from tests.helpers.constants import (
    PREFECT_FLOW_HEARTBEAT_FREQUENCY_SECONDS,
    PREFECT_SERVER_NONESSENTIAL_SERVICE_ENV_VARS,
    PREFECT_TEST_SERVER_PORT_RANGE,
)
from tests.helpers.file_repo import FileRepo
from tests.helpers.utils import find_available_prefect_port


@pytest.fixture(scope="class", autouse=True)
def _collect_cyclic_garbage() -> Generator[None, None, None]:
    """Collect reference cycles and return freed pages to the OS after each test class.

    The async neo4j driver and the query machinery create cyclic garbage faster than the
    default gen-2 GC cadence collects it; on a large heap hundreds of MB of dead objects
    can sit between collections. Collecting alone is not enough: freed pages stay in the
    allocator, so worker RSS ratchets to its high-water mark, which caps how many xdist
    workers fit on a host. malloc_trim hands the freed pages back to the OS.
    """
    yield
    gc.collect()
    with contextlib.suppress(OSError):  # non-glibc platform
        ctypes.CDLL("libc.so.6").malloc_trim(0)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Overrides pytest default function scoped event loop."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


async def load_infrastructure_schema(db: InfrahubDatabase) -> None:
    base_dir = get_models_dir() / "base"

    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()

    for file_name in base_dir.iterdir():
        file_path = base_dir / file_name

        if file_path.suffix in (".yml", ".yaml"):
            schema_txt = file_path.read_text(encoding="utf-8")
            loaded_schema = yaml.safe_load(schema_txt)
            tmp_schema.load_schema(schema=SchemaRoot(**loaded_schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)


@pytest.fixture(scope="module")
async def init_db_base(db: InfrahubDatabase) -> None:
    await delete_all_nodes(db=db)
    await first_time_initialization(db=db)
    await initialization(db=db)


class IntegrationHelper:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
        self._admin_headers: dict[str, Any] = {}

    async def admin_headers(self) -> dict[str, Any]:
        if not self._admin_headers:
            self._admin_headers = {"X-INFRAHUB-KEY": await self.create_token()}
        return self._admin_headers

    async def create_token(self, account_name: str | None = None) -> str:
        token = str(UUIDT())
        account_name = account_name or "admin"
        response = await NodeManager.query(
            schema=InfrahubKind.ACCOUNT, db=self.db, filters={"name__value": account_name}, limit=1
        )
        account = response[0]
        account_token = await Node.init(db=self.db, schema=InfrahubKind.ACCOUNTTOKEN)
        await account_token.new(db=self.db, token=token, account=account)
        await account_token.save(db=self.db)
        return token


@pytest.fixture(scope="class")
def integration_helper(db: InfrahubDatabase) -> IntegrationHelper:
    return IntegrationHelper(db=db)


@pytest.fixture(scope="session")
def git_sources_dir(tmp_path_factory: TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("sources")


@pytest.fixture(scope="session")
def git_repos_dir(tmp_path_factory: TempPathFactory) -> Path:
    repos_dir = tmp_path_factory.mktemp("repositories")
    config.SETTINGS.git.repositories_directory = str(repos_dir)
    return repos_dir


@pytest.fixture(scope="session")
def git_repo_infrahub_demo_edge_integration(git_sources_dir: Path) -> FileRepo:
    """Git Repository used as part of the  demo-edge tutorial."""
    return FileRepo(name="infrahub-demo-edge-integration", sources_directory=git_sources_dir)


@pytest.fixture(scope="session")
def git_repo_car_dealership(git_sources_dir: Path) -> FileRepo:
    """Simple Git Repository used for testing."""
    return FileRepo(name="car-dealership", sources_directory=git_sources_dir)


@pytest.fixture(scope="session", autouse=True)
def prefect_test_fixture() -> Generator:
    os.environ["PREFECT_SERVER_API_MAX_PARAMETER_SIZE"] = "0"
    os.environ["PREFECT_FLOWS_HEARTBEAT_FREQUENCY"] = PREFECT_FLOW_HEARTBEAT_FREQUENCY_SECONDS
    os.environ.update(PREFECT_SERVER_NONESSENTIAL_SERVICE_ENV_VARS)

    with (
        patch.object(SubprocessASGIServer, "_port_range", PREFECT_TEST_SERVER_PORT_RANGE),
        patch("prefect.testing.utilities._find_available_port", find_available_prefect_port),
        prefect_test_harness(server_startup_timeout=180),
    ):
        yield
