import asyncio
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import pytest
import yaml
from infrahub_sdk import UUIDT

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.utils import get_models_dir


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
async def db() -> AsyncGenerator[InfrahubDatabase, None]:
    driver = InfrahubDatabase(driver=await get_db(retry=1))

    yield driver

    await driver.close()


async def load_infrastructure_schema(db: InfrahubDatabase):
    base_dir = get_models_dir() / "base"

    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()

    for file_name in os.listdir(base_dir):
        file_path = os.path.join(base_dir, file_name)

        if file_path.endswith((".yml", ".yaml")):
            schema_txt = Path(file_path).read_text(encoding="utf-8")
            loaded_schema = yaml.safe_load(schema_txt)
            tmp_schema.load_schema(schema=SchemaRoot(**loaded_schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)


@pytest.fixture(scope="module")
async def init_db_infra(db: InfrahubDatabase):
    await delete_all_nodes(db=db)
    await first_time_initialization(db=db)
    await load_infrastructure_schema(db=db)
    await initialization(db=db)


@pytest.fixture(scope="module")
async def init_db_base(db: InfrahubDatabase):
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

    async def create_token(self, account_name: Optional[str] = None) -> str:
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
