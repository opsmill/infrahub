import os
import asyncio
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from neo4j import AsyncGraphDatabase

import infrahub.config as config

from infrahub.main import app

from infrahub.core.node import Node
from infrahub.core.initialization import first_time_initialization, initialization, create_branch
from infrahub.core.utils import delete_all_nodes
from infrahub.test_data import dataset01 as ds01

NEO4J_PROTOCOL = os.environ.get("NEO4J_PROTOCOL", "neo4j")  # neo4j+s
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "admin")
NEO4J_ADDRESS = os.environ.get("NEO4J_ADDRESS", "localhost")
NEO4J_PORT = os.environ.get("NEO4J_PORT", 7687)  # 443
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "infrahub")

URL = f"{NEO4J_PROTOCOL}://{NEO4J_ADDRESS}"


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    db = AsyncGraphDatabase.driver(URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    yield db

    await db.close()


@pytest.fixture(scope="module")
async def client():
    return TestClient(app)


@pytest.fixture(scope="module")
async def session(db):

    session = db.session(database=config.SETTINGS.database.database)

    yield session

    await session.close()


@pytest.fixture(scope="module")
async def init_db_infra(session):
    await delete_all_nodes(session=session)
    await first_time_initialization(session=session, load_infrastructure_models=True)
    await initialization(session=session)


@pytest.fixture(scope="module")
async def init_db_base(session):
    await delete_all_nodes(session=session)
    await first_time_initialization(session=session, load_infrastructure_models=False)
    await initialization(session=session)


@pytest.fixture(scope="module")
async def client():
    return TestClient(app)


@pytest.fixture(scope="module")
async def base_dataset(session):

    branch1 = await create_branch(branch_name="branch01", session=session)

    query_string = """
    query {
        branch {
            id
            name
        }
    }
    """
    obj = await Node.init(schema="GraphQLQuery", session=session)
    await obj.new(session=session, name="test_query2", description="test query", query=query_string)
    await obj.save(session=session)


@pytest_asyncio.fixture(scope="module")
async def dataset01(session, init_db_infra):
    await ds01.load_data(session=session)
