import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from fast_depends import Provider
from fast_depends import dependency_provider as provider
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT
from prefect.client.orchestration import PrefectClient

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_account,
    create_default_account_groups,
    create_default_branch,
    create_global_branch,
    create_root_node,
    initialization,
)
from infrahub.core.protocols import CoreAccount
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.graphql.registry import registry as graphql_registry
from infrahub.server import app, lifespan
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_cache, build_client, build_message_bus, build_workflow
from infrahub.workflows.initialization import setup_task_manager
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusSimulator
from tests.helpers.events import query_events_by_name

from .test_client import InfrahubTestClient


class TestInfrahub:
    default_services: InfrahubServices

    @pytest.fixture(scope="class")
    def local_storage_dir(self, tmpdir_factory: pytest.TempdirFactory) -> Path:
        storage_dir = Path(tmpdir_factory.getbasetemp().strpath) / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
        config.SETTINGS.storage.local.path_ = storage_dir

        return storage_dir

    @pytest.fixture(scope="class")
    async def default_branch(self, local_storage_dir: Path, db: InfrahubDatabase) -> Branch:
        registry.delete_all()
        await delete_all_nodes(db=db)
        await create_root_node(db=db)
        branch = await create_default_branch(db=db)
        await create_global_branch(db=db)
        registry.schema = SchemaManager()
        return branch


class TestInfrahubApp(TestInfrahub):
    @pytest.fixture(scope="class")
    def api_admin_token(self) -> str:
        return str(UUIDT())

    @pytest.fixture(scope="class")
    def api_bot_token(self) -> str:
        return str(UUIDT())

    @pytest.fixture(scope="class")
    def api_unprivileged_token(self) -> str:
        return str(UUIDT())

    @pytest.fixture(scope="class")
    def dependency_provider(self) -> Provider:
        return provider

    @pytest.fixture(scope="class")
    async def bus_simulator(
        self, db: InfrahubDatabase, dependency_provider: Provider
    ) -> AsyncGenerator[BusSimulator, None]:
        # Creating another service object to get service correctly initialized is a hack.
        # We should either reuse `service` fixture (leading to circular fixture dependencies issue atm),
        # or ideally properly patch production code responsible for Bus instantiation instead
        bus = BusSimulator()
        _ = await InfrahubServices.new(database=db, workflow=WorkflowLocalExecution(), message_bus=bus)
        config.OVERRIDE.message_bus = bus
        with dependency_provider.scope(build_message_bus, lambda: bus):
            yield bus

    @pytest.fixture(scope="class")
    async def memory_cache(
        self, db: InfrahubDatabase, dependency_provider: Provider
    ) -> AsyncGenerator[MemoryCache, None]:
        cache = MemoryCache()
        config.OVERRIDE.cache = cache
        with dependency_provider.scope(build_cache, lambda: cache):
            yield cache

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_local(
        self, prefect: Generator[str, None, None], dependency_provider: Provider
    ) -> AsyncGenerator[WorkflowLocalExecution, None]:
        original = config.OVERRIDE.workflow
        workflow = WorkflowLocalExecution()
        await setup_task_manager()
        config.OVERRIDE.workflow = workflow
        with dependency_provider.scope(build_workflow, lambda: workflow):
            yield workflow
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: InfrahubTestClient) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    async def register_internal_schema(self, db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
        schema = SchemaRoot(**internal_schema)
        schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        await default_branch.save(db=db)
        return schema_branch

    @pytest.fixture(scope="class")
    async def register_core_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_internal_schema: SchemaBranch
    ) -> SchemaBranch:
        schema = SchemaRoot(**core_models)
        schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        await default_branch.save(db=db)
        return schema_branch

    @pytest.fixture(scope="class")
    async def test_client(
        self, initialize_registry: None, redis: dict[int, int] | None, nats: dict[int, int] | None
    ) -> AsyncGenerator[InfrahubTestClient, None]:
        # NOTE 1: lifespan call emits an ERROR because it calls registry-webhook-config-refresh flow within a local worker
        # while services.service.client is not set. There might be a design issue here: a client is needed while
        # the app is being initialized.
        # NOTE 2: FastAPI does not have an asynchronous TestClient, thus we rely on httpx.AsyncClient which does not trigger
        # lifespan events (see https://fastapi.tiangolo.com/advanced/async-tests/#in-detail).
        async with lifespan(app):
            yield InfrahubTestClient(app=app, base_url="http://testserver")

    @pytest.fixture(scope="class")
    async def client(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> AsyncGenerator[InfrahubClient, None]:
        config = Config(
            api_token=api_admin_token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )

        sdk_client = InfrahubClient(config=config)

        # Some tests rely on infrahub worker which runs locally during testing. Thus, code supposed to run
        # on worker rely on server's `services.service`, which is not initialized with a client,
        # instead of the worker one. Thus, we temporarily set `services.service.client`
        # here to mock worker's `services.service`.
        assert isinstance(service.workflow, WorkflowLocalExecution), (
            "These tests are currently meant to run with a local worker"
        )

        service._client = sdk_client
        with dependency_provider.scope(build_client, lambda: sdk_client):
            yield sdk_client

    @pytest.fixture(scope="class")
    async def bot_client(
        self,
        test_client: InfrahubTestClient,
        api_bot_token: str,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> InfrahubClient:
        """Similar to `client` fixture but using bot account credentials.

        The reason for having this fixture is to be able to differentiate actions performed by
        admin user vs another user in tests.
        """
        config = Config(
            api_token=api_bot_token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )

        return InfrahubClient(config=config)

    @pytest.fixture(scope="class")
    async def unprivileged_client(
        self,
        test_client: InfrahubTestClient,
        api_unprivileged_token: str,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> InfrahubClient:
        config = Config(
            api_token=api_unprivileged_token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )

        sdk_client = InfrahubClient(config=config)
        return sdk_client

    @pytest.fixture(scope="class")
    async def admin_account(
        self,
        db: InfrahubDatabase,
        register_core_schema: SchemaBranch,
        bus_simulator: BusSimulator,
        api_admin_token: str,
    ) -> CoreAccount:
        return await create_account(
            db=db, name="admin", password=config.SETTINGS.initial.admin_password, token_value=api_admin_token
        )

    @pytest.fixture(scope="class")
    async def bot_account(
        self,
        db: InfrahubDatabase,
        register_core_schema: SchemaBranch,
        bus_simulator: BusSimulator,
        api_bot_token: str,
    ) -> CoreAccount:
        return await create_account(
            db=db, name="infrahub-bot", password=config.SETTINGS.initial.admin_password, token_value=api_bot_token
        )

    @pytest.fixture(scope="class")
    async def initialize_registry(
        self,
        db: InfrahubDatabase,
        register_core_schema: SchemaBranch,
        bus_simulator: BusSimulator,
        admin_account: CoreAccount,
        bot_account: CoreAccount,
        api_unprivileged_token: str,
    ) -> None:
        unprivileged_account = await create_account(
            db=db, name="unprivileged", password="testing_unprivileged_password", token_value=api_unprivileged_token
        )

        await create_default_account_groups(
            db=db, admin_accounts=[admin_account, bot_account], accounts=[unprivileged_account]
        )

        # This call emits a warning related to the fact database index manager has not been initialized.
        graphql_registry.clear_cache()
        await initialization(db=db)

    async def assert_event(self, prefect_client: PrefectClient, event_name: str) -> None:
        for _ in range(10):
            events = await query_events_by_name(client=prefect_client, event_name=event_name)
            if len(events) == 1:
                return
            await asyncio.sleep(1)

        pytest.fail(f"unable to find prefect event '{event_name}'")
