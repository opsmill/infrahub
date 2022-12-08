import os
import asyncio
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from neo4j import AsyncGraphDatabase, AsyncDriver, GraphDatabase, Driver

import infrahub.config as config

from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.main import app
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


@pytest_asyncio.fixture(scope="module")
async def db():
    db = AsyncGraphDatabase.driver(URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    yield db

    await db.close()


@pytest_asyncio.fixture(scope="module")
async def session(db):

    session = db.session(database=config.SETTINGS.database.database)

    yield session

    await session.close()


@pytest_asyncio.fixture(scope="module")
async def init_db(session):
    await delete_all_nodes(session=session)
    await first_time_initialization(session=session)
    await initialization(session=session)


@pytest_asyncio.fixture(scope="module")
async def client(init_db):
    # api_client = TestClient(app)
    return TestClient(app)


@pytest_asyncio.fixture(scope="module")
async def dataset01(session, init_db):
    await ds01.load_data(session=session)
