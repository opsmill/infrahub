import asyncio
import os
from pathlib import Path

import pytest
import yaml

import infrahub.config as config
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import delete_all_nodes
from infrahub.database import get_db
from infrahub.utils import get_models_dir


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    driver = await get_db()

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

    schema = SchemaRoot(**infra_schema)
    schema.extend_nodes_with_interfaces()

    await SchemaManager.register_schema_to_registry(schema)
    await SchemaManager.load_schema_to_db(schema, session=session)


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
