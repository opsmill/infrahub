import asyncio

import pytest

import infrahub.config as config
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.node import Node
from infrahub.core.utils import delete_all_nodes
from infrahub.database import AsyncSession, get_db
from infrahub_client.schema import NodeSchema

TEST_DATABASE = "infrahub.testing"

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def execute_before_any_test():
    config.load_and_exit()
    config.SETTINGS.database.database = TEST_DATABASE
    config.SETTINGS.broker.enable = False
    config.SETTINGS.main.internal_address = "http://mock"


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


@pytest.fixture(scope="module")
async def init_db_base(session: AsyncSession):
    await delete_all_nodes(session=session)
    await first_time_initialization(session=session)
    await initialization(session=session)


@pytest.fixture
async def location_schema() -> NodeSchema:
    data = {
        "name": "location",
        "kind": "Location",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "type", "kind": "String"},
        ],
        "relationships": [
            {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            {"name": "primary_tag", "peer": "Tag", "optional": True, "cardinality": "one"},
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def tag_blue(session: AsyncSession) -> Node:
    obj = await Node.init(schema="Tag", session=session)
    await obj.new(session=session, name="Blue")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def tag_red(session: AsyncSession) -> Node:
    obj = await Node.init(schema="Tag", session=session)
    await obj.new(session=session, name="Red")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def tag_green(session: AsyncSession) -> Node:
    obj = await Node.init(schema="Tag", session=session)
    await obj.new(session=session, name="Green")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def first_account(session: AsyncSession) -> Node:
    obj = await Node.init(session=session, schema="Account")
    await obj.new(session=session, name="First Account", type="Git", password="TestPassword123")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def second_account(session: AsyncSession) -> Node:
    obj = await Node.init(session=session, schema="Account")
    await obj.new(session=session, name="Second Account", type="Git", password="TestPassword123")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def repo01(session: AsyncSession) -> Node:
    obj = await Node.init(session=session, schema="Repository")
    await obj.new(session=session, name="repo01", location="https://github.com/my/repo.git")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def repo99(session: AsyncSession) -> Node:
    obj = await Node.init(session=session, schema="Repository")
    await obj.new(session=session, name="repo99", location="https://github.com/my/repo99.git")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def gqlquery01(session: AsyncSession) -> Node:
    obj = await Node.init(session=session, schema="GraphQLQuery")
    await obj.new(session=session, name="query01", query="query { device { name { value }}}")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def gqlquery02(session: AsyncSession, repo01: Node, tag_blue: Node, tag_red: Node) -> Node:
    obj = await Node.init(session=session, schema="GraphQLQuery")
    await obj.new(
        session=session,
        name="query02",
        query="query { device { name { value }}}",
        repository=repo01,
        tags=[tag_blue, tag_red],
    )
    await obj.save(session=session)
    return obj
