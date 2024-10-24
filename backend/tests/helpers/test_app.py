import os
from typing import Generator

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_account,
    create_default_branch,
    create_global_branch,
    create_root_node,
    create_super_administrator_role,
    create_super_administrators_group,
    initialization,
)
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.server import app, app_initialization
from infrahub.services import services
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.message_bus import BusSimulator

from .test_client import InfrahubTestClient


class TestInfrahub:
    @pytest.fixture(scope="class")
    def local_storage_dir(self, tmpdir_factory: pytest.TempdirFactory) -> str:
        storage_dir = os.path.join(str(tmpdir_factory.getbasetemp().strpath), "storage")
        if not os.path.exists(storage_dir):
            os.mkdir(storage_dir)

        config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
        config.SETTINGS.storage.local.path_ = storage_dir

        return storage_dir

    @pytest.fixture(scope="class")
    async def default_branch(self, local_storage_dir: str, db: InfrahubDatabase) -> Branch:
        registry.delete_all()
        await delete_all_nodes(db=db)
        await create_root_node(db=db)
        branch = await create_default_branch(db=db)
        await create_global_branch(db=db)
        registry.schema = SchemaManager()
        return branch


class TestInfrahubApp(TestInfrahub):
    @pytest.fixture(scope="class")
    def api_token(self) -> str:
        return str(UUIDT())

    @pytest.fixture(scope="class")
    def bus_simulator(self, db: InfrahubDatabase) -> Generator[BusSimulator, None, None]:
        bus = BusSimulator(database=db, workflow=WorkflowLocalExecution())
        original = config.OVERRIDE.message_bus
        config.OVERRIDE.message_bus = bus
        yield bus
        config.OVERRIDE.message_bus = original

    @pytest.fixture(scope="class", autouse=True)
    def workflow_local(self) -> Generator[WorkflowLocalExecution, None, None]:
        original = config.OVERRIDE.workflow
        workflow = WorkflowLocalExecution()
        config.OVERRIDE.workflow = workflow
        yield workflow
        config.OVERRIDE.workflow = original

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
    ) -> InfrahubTestClient:
        # This call emits an ERROR because it calls registry-webhook-config-refresh flow within a local worker
        # while services.service.client is not set. There might be a design issue here: a client is needed while
        # the app is being initialized.
        await app_initialization(app)
        return InfrahubTestClient(app=app)

    @pytest.fixture(scope="class")
    async def client(
        self, test_client: InfrahubTestClient, api_token: str, bus_simulator: BusSimulator
    ) -> InfrahubClient:
        config = Config(
            api_token=api_token, requester=test_client.async_request, sync_requester=test_client.sync_request
        )

        sdk_client = InfrahubClient(config=config)

        bus_simulator.service._client = sdk_client

        # Some tests rely on infrahub worker which runs locally during testing. Thus, code supposed to run
        # on worker rely on server's `services.service`, which is not initialized with a client,
        # instead of the worker one. Thus, we temporarily set `services.service.client`
        # here to mock worker's `services.service`.
        assert isinstance(
            services.service.workflow, WorkflowLocalExecution
        ), "These tests are currently meant to run with a local worker"
        original_service_client = services.service._client
        services.service.set_client(sdk_client)
        yield sdk_client
        services.service.set_client(original_service_client)

    @pytest.fixture(scope="class")
    async def initialize_registry(
        self, db: InfrahubDatabase, register_core_schema: SchemaBranch, bus_simulator: BusSimulator, api_token: str
    ) -> None:
        admin_account = await create_account(
            db=db, name="admin", password=config.SETTINGS.initial.admin_password, token_value=api_token
        )
        administrator_role = await create_super_administrator_role(db=db)
        await create_super_administrators_group(db=db, role=administrator_role, admin_accounts=[admin_account])

        # This call emits a warning related to the fact database index manager has not been initialized.
        await initialization(db=db)
