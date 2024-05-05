import os
from typing import Generator

import pytest
from infrahub_sdk import UUIDT, Config, InfrahubClient

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_account,
    create_default_branch,
    create_global_branch,
    create_root_node,
    initialization,
)
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema_manager import SchemaBranch, SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.server import app, app_initialization
from tests.adapters.message_bus import BusSimulator

from .test_client import InfrahubTestClient


class TestInfrahubApp:
    @pytest.fixture(scope="class")
    def api_token(self) -> str:
        return str(UUIDT())

    @pytest.fixture(scope="class")
    def local_storage_dir(self, tmpdir_factory: pytest.TempdirFactory) -> str:
        storage_dir = os.path.join(str(tmpdir_factory.getbasetemp().strpath), "storage")
        if not os.path.exists(storage_dir):
            os.mkdir(storage_dir)

        config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
        config.SETTINGS.storage.local.path_ = storage_dir

        return storage_dir

    @pytest.fixture(scope="class")
    def bus_simulator(self, db: InfrahubDatabase) -> Generator[BusSimulator, None, None]:
        bus = BusSimulator(database=db)
        original = config.OVERRIDE.message_bus
        config.OVERRIDE.message_bus = bus
        yield bus
        config.OVERRIDE.message_bus = original

    @pytest.fixture(scope="class")
    async def default_branch(self, local_storage_dir: str, db: InfrahubDatabase) -> Branch:
        registry.delete_all()
        await delete_all_nodes(db=db)
        await create_root_node(db=db)
        branch = await create_default_branch(db=db)
        await create_global_branch(db=db)
        registry.schema = SchemaManager()
        return branch

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
        self,
        initialize_registry: None,
    ) -> InfrahubTestClient:
        await app_initialization(app)
        return InfrahubTestClient(app=app)

    @pytest.fixture(scope="class")
    async def client(
        self, test_client: InfrahubTestClient, api_token: str, bus_simulator: BusSimulator
    ) -> InfrahubClient:
        config = Config(
            api_token=api_token, requester=test_client.async_request, sync_requester=test_client.sync_request
        )

        sdk_client = await InfrahubClient.init(config=config)

        bus_simulator.service._client = sdk_client

        return sdk_client

    @pytest.fixture(scope="class")
    async def initialize_registry(
        self, db: InfrahubDatabase, register_core_schema: SchemaBranch, bus_simulator: BusSimulator, api_token: str
    ) -> None:
        await create_account(
            db=db,
            name="admin",
            password=config.SETTINGS.security.initial_admin_password,
            token_value=api_token,
        )

        await initialization(db=db)
