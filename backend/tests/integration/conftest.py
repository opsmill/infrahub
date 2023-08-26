import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import yaml
from neo4j import AsyncSession

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import delete_all_nodes
from infrahub.database import get_db
from infrahub.utils import get_models_dir
from infrahub_client import UUIDT


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    driver = await get_db(retry=1)

    yield driver

    await driver.close()


@pytest.fixture(scope="module")
async def session(db):
    session = db.session(database=config.SETTINGS.database.database)

    yield session

    await session.close()


async def load_infrastructure_schema(session):
    models_dir = get_models_dir()

    schema_txt = Path(os.path.join(models_dir, "infrastructure_base.yml")).read_text()
    infra_schema = yaml.safe_load(schema_txt)

    default_branch_name = config.SETTINGS.main.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()
    tmp_schema.load_schema(schema=SchemaRoot(**infra_schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(
        schema=tmp_schema, session=session, branch=default_branch_name, update_db=True
    )


@pytest.fixture(scope="module")
async def init_db_infra(session):
    await delete_all_nodes(session=session)
    await first_time_initialization(session=session)
    await load_infrastructure_schema(session=session)
    await initialization(session=session)


@pytest.fixture(scope="module")
async def init_db_base(session):
    await delete_all_nodes(session=session)
    await first_time_initialization(session=session)
    await initialization(session=session)


class IntegrationHelper:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._admin_headers = {}

    async def admin_headers(self) -> Dict[str, Any]:
        if not self._admin_headers:
            self._admin_headers = {"X-INFRAHUB-KEY": await self.create_token()}
        return self._admin_headers

    async def create_token(self, account_name: Optional[str] = None) -> str:
        token = str(UUIDT())
        account_name = account_name or "admin"
        response = await NodeManager.query(
            schema="CoreAccount",
            session=self.session,
            filters={"name__value": account_name},
            limit=1,
        )
        account = response[0]
        account_token = await Node.init(session=self.session, schema="InternalAccountToken")
        await account_token.new(
            session=self.session,
            token=token,
            account=account,
        )
        await account_token.save(session=self.session)
        return token


@pytest.fixture(scope="class")
def integration_helper(session) -> IntegrationHelper:
    return IntegrationHelper(session=session)
