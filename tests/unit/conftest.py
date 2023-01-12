import asyncio

import pendulum
import pytest

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_default_branch,
    first_time_initialization,
    initialization,
)
from infrahub.core.manager import SchemaManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema, SchemaRoot, core_models, internal_schema
from infrahub.core.utils import delete_all_nodes
from infrahub.database import execute_write_query_async, get_db
from infrahub.test_data import dataset01 as ds01

# NEO4J_PROTOCOL = os.environ.get("NEO4J_PROTOCOL", "neo4j")  # neo4j+s
# NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
# NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "admin")
# NEO4J_ADDRESS = os.environ.get("NEO4J_ADDRESS", "localhost")
# NEO4J_PORT = os.environ.get("NEO4J_PORT", 7687)  # 443
# NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "infrahub")

# URL = f"{NEO4J_PROTOCOL}://{NEO4J_ADDRESS}"


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    db = await get_db()

    yield db

    await db.close()


@pytest.fixture
async def session(db):

    session = db.session(database=config.SETTINGS.database.database)

    yield session

    await session.close()


@pytest.fixture
async def simple_dataset_01(session, empty_database):

    await create_default_branch(session)

    params = {
        "branch": "main",
        "time1": pendulum.now(tz="UTC").to_iso8601_string(),
        "time2": pendulum.now(tz="UTC").subtract(seconds=5).to_iso8601_string(),
    }

    query = """
    MATCH (b:Branch { name: $branch })
    CREATE (c:Car { uuid: "5ffa45d4" })
    CREATE (c)-[r:IS_PART_OF {from: $time1}]->(b)

    CREATE (at1:Attribute:AttributeLocal { uuid: "ee04c93a", type: "Str", name: "name"})
    CREATE (at2:Attribute:AttributeLocal { uuid: "924786c3", type: "Int", name: "nbr_seats"})
    CREATE (c)-[:HAS_ATTRIBUTE {branch: $branch, from: $time1}]->(at1)
    CREATE (c)-[:HAS_ATTRIBUTE {branch: $branch, from: $time1}]->(at2)

    CREATE (av11:AttributeValue { uuid: "f6b745c3", value: "accord"})
    CREATE (av12:AttributeValue { uuid: "36100ef6", value: "volt"})
    CREATE (av21:AttributeValue { uuid: "d8d49788",value: 5})
    CREATE (at1)-[:HAS_VALUE {branch: $branch, from: $time1, to: $time2}]->(av11)
    CREATE (at1)-[:HAS_VALUE {branch: $branch, from: $time2 }]->(av12)
    CREATE (at2)-[:HAS_VALUE {branch: $branch, from: $time1 }]->(av21)

    RETURN c, at1, at2
    """

    await execute_write_query_async(session=session, query=query, params=params)


@pytest.fixture
async def base_dataset_02(session, default_branch, car_person_schema):
    """This Dataset includes:
    - 4 timestamps
      * time0 is now
      * time_m20 is now - 20s
      * time_m40 is now - 40s
      * time_m60 is now - 60s

    - 2 branches, main and branch1.
        - branch1 was created at time_m40

    - 2 Cars in Main and 1 in Branch1
        - Car1 was created at time_m60 in main
        - Car2 was created at time_m20 in main
        - Car3 was created at time_m40 in branch1

    - 2 Persons in Main

    """

    time0 = pendulum.now(tz="UTC")

    # Create new Branch
    branch1 = Branch(
        name="branch1",
        status="OPEN",
        description="Second Branch",
        is_default=False,
        is_data_only=True,
        branched_from=time0.subtract(seconds=40).to_iso8601_string(),
    )
    await branch1.save(session=session)
    registry.branch[branch1.name] = branch1

    params = {
        "main_branch": "main",
        "branch1": "branch1",
        "time0": time0.to_iso8601_string(),
        "time_m10": time0.subtract(seconds=10).to_iso8601_string(),
        "time_m20": time0.subtract(seconds=20).to_iso8601_string(),
        "time_m25": time0.subtract(seconds=25).to_iso8601_string(),
        "time_m30": time0.subtract(seconds=30).to_iso8601_string(),
        "time_m35": time0.subtract(seconds=35).to_iso8601_string(),
        "time_m40": time0.subtract(seconds=40).to_iso8601_string(),
        "time_m50": time0.subtract(seconds=50).to_iso8601_string(),
        "time_m60": time0.subtract(seconds=60).to_iso8601_string(),
    }

    query = """
    MATCH (b0:Branch { name: $main_branch })
    MATCH (b1:Branch { name: $branch1 })

    CREATE (c1:Car { uuid: "c1" })
    CREATE (c1)-[:IS_PART_OF { from: $time_m60, status: "active" }]->(b0)

    CREATE (bool_true:Boolean { value: true })
    CREATE (bool_false:Boolean { value: false })

    CREATE (atvf:AttributeValue { value: false })
    CREATE (atvt:AttributeValue { value: true })
    CREATE (atv44:AttributeValue { value: "#444444" })

    CREATE (c1at1:Attribute:AttributeLocal { uuid: "c1at1", type: "Str", name: "name"})
    CREATE (c1at2:Attribute:AttributeLocal { uuid: "c1at2", type: "Int", name: "nbr_seats"})
    CREATE (c1at3:Attribute:AttributeLocal { uuid: "c1at3", type: "Bool", name: "is_electric"})
    CREATE (c1at4:Attribute:AttributeLocal { uuid: "c1at4", type: "Str", name: "color"})
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at1)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at2)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at3)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at4)

    CREATE (c1av11:AttributeValue { value: "accord"})
    CREATE (c1av12:AttributeValue { value: "volt"})
    CREATE (c1av21:AttributeValue { value: 5})
    CREATE (c1av22:AttributeValue { value: 4})

    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60, to: $time_m20}]->(c1av11)
    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c1av12)
    CREATE (c1at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at2)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(c1av21)
    CREATE (c1at2)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m20 }]->(c1av22)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m20 }]->(bool_true)
    CREATE (c1at2)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at3)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60}]->(atvt)
    CREATE (c1at3)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at3)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at4)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60}]->(atv44)
    CREATE (c1at4)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at4)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c2:Car { uuid: "c2" })
    CREATE (c2)-[:IS_PART_OF {from: $time_m20, status: "active"}]->(b0)

    CREATE (c2at1:Attribute:AttributeLocal { uuid: "c2at1", type: "Str", name: "name"})
    CREATE (c2at2:Attribute:AttributeLocal { uuid: "c2at2", type: "Int", name: "nbr_seats"})
    CREATE (c2at3:Attribute:AttributeLocal { uuid: "c2at3", type: "Bool", name: "is_electric"})
    CREATE (c2at4:Attribute:AttributeLocal { uuid: "c2at4", type: "Str", name: "color"})
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at1)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at2)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at3)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at4)

    CREATE (c2av11:AttributeValue { value: "odyssey"})
    CREATE (c2av21:AttributeValue { value: 8})

    CREATE (c2at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c2av11)
    CREATE (c2at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at2)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c2av21)
    CREATE (c2at2)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at2)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at3)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(atvf)
    CREATE (c2at3)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at3)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at4)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(atv44)
    CREATE (c2at4)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at4)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c3:Car { uuid: "c3" })
    CREATE (c3)-[:IS_PART_OF {from: $time_m40, status: "active"}]->(b1)

    CREATE (c3at1:Attribute:AttributeLocal { uuid: "c3at1", type: "Str", name: "name"})
    CREATE (c3at2:Attribute:AttributeLocal { uuid: "c3at2", type: "Int", name: "nbr_seats"})
    CREATE (c3at3:Attribute:AttributeLocal { uuid: "c3at3", type: "Bool", name: "is_electric"})
    CREATE (c3at4:Attribute:AttributeLocal { uuid: "c3at4", type: "Str", name: "color"})
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at1)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at2)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at3)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at4)

    CREATE (c3av11:AttributeValue { uuid: "c3av11", value: "volt"})
    CREATE (c3av21:AttributeValue { uuid: "c3av21", value: 4})

    CREATE (c3at1)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(c3av11)
    CREATE (c3at1)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at1)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at2)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(c3av21)
    CREATE (c3at2)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at2)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at3)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(atvf)
    CREATE (c3at3)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at3)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at4)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(atv44)
    CREATE (c3at4)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at4)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (p1:Person { uuid: "p1" })
    CREATE (p1)-[:IS_PART_OF {from: $time_m60, status: "active"}]->(b0)
    CREATE (p1at1:Attribute:AttributeLocal { uuid: "p1at1", type: "Str", name: "name"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(p1at1)
    CREATE (p1av11:AttributeValue { uuid: "p1av11", value: "John Doe"})
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(p1av11)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p2:Person { uuid: "p2" })
    CREATE (p2)-[:IS_PART_OF {from: $time_m60, status: "active"}]->(b0)
    CREATE (p2at1:Attribute:AttributeLocal { uuid: "p2at1", type: "Str", name: "name"})
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(p2at1)
    CREATE (p2av11:AttributeValue { uuid: "p2av11", value: "Jane Doe"})
    CREATE (p2at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(p2av11)
    CREATE (p2at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p2at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p3:Person { uuid: "p3" })
    CREATE (p3)-[:IS_PART_OF {from: $time_m60, status: "active"}]->(b0)
    CREATE (p3at1:Attribute:AttributeLocal { uuid: "p3at1", type: "Str", name: "name"})
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(p3at1)
    CREATE (p3av11:AttributeValue { uuid: "p3av11", value: "Bill"})
    CREATE (p3at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(p3av11)
    CREATE (p3at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p3at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (r1:Relationship { uuid: "r1", type: "car_person"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, status: "active", from: $time_m60 }]->(r1)
    CREATE (c1)-[:IS_RELATED { branch: $main_branch, status: "active", from: $time_m60 }]->(r1)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60, to: $time_m30 }]->(bool_false)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m30 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m20 }]->(bool_false)

    CREATE (r2:Relationship { uuid: "r2", type: "car_person"})
    CREATE (p1)-[:IS_RELATED { branch: $branch1, status: "active", from: $time_m20 }]->(r2)
    CREATE (c2)-[:IS_RELATED { branch: $branch1, status: "active", from: $time_m20 }]->(r2)
    CREATE (r2)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (r2)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m20 }]->(bool_true)

    RETURN c1, c2, c3
    """

    await execute_write_query_async(session=session, query=query, params=params)

    return params


@pytest.fixture
async def car_person_schema(session):

    SCHEMA = {
        "nodes": [
            {
                "name": "car",
                "kind": "Car",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "nbr_seats", "kind": "Integer"},
                    {"name": "color", "kind": "String", "default_value": "#444444"},
                    {"name": "is_electric", "kind": "Boolean"},
                ],
                "relationships": [
                    {"name": "owner", "peer": "Person", "optional": False, "cardinality": "one"},
                ],
            },
            {
                "name": "person",
                "kind": "Person",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "height", "kind": "Integer", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "Car", "cardinality": "many"}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.nodes:
        await registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def person_tag_schema(session):

    SCHEMA = {
        "nodes": [
            {
                "name": "tag",
                "kind": "Tag",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "description", "kind": "String", "optional": True},
                ],
            },
            {
                "name": "person",
                "kind": "Person",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "firstname", "kind": "String"},
                    {"name": "lastname", "kind": "String"},
                ],
                "relationships": [
                    {"name": "tags", "peer": "Tag", "cardinality": "many"},
                    {"name": "primary_tag", "peer": "Tag", "identifier": "person_primary_tag", "cardinality": "one"},
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.nodes:
        await registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def criticality_schema(session):

    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "level", "kind": "Integer"},
            {"name": "color", "kind": "String", "default_value": "#444444"},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }

    node = NodeSchema(**SCHEMA)
    await registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def fruit_tag_schema(session):

    SCHEMA = {
        "nodes": [
            {
                "name": "tag",
                "kind": "Tag",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "color", "kind": "String", "default_value": "#444444"},
                    {"name": "description", "kind": "String", "optional": True},
                ],
            },
            {
                "name": "fruit",
                "kind": "Fruit",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "description", "kind": "String", "optional": True},
                ],
                "relationships": [{"name": "tags", "peer": "Tag", "cardinality": "many", "optional": False}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.nodes:
        await registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def empty_database(session):
    await delete_all_nodes(session=session)


@pytest.fixture
async def init_db(empty_database, session):
    await first_time_initialization(session=session)
    await initialization(session=session)


@pytest.fixture
async def default_branch(empty_database, session) -> Branch:
    return await create_default_branch(session=session)


@pytest.fixture
async def register_core_models_schema():

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema)

    schema = SchemaRoot(**core_models)
    await SchemaManager.register_schema_to_registry(schema=schema)


@pytest.fixture
async def register_account_schema(session):

    SCHEMAS_TO_REGISTER = ["Account", "AccountToken", "Group"]

    account_schemas = [node for node in core_models["nodes"] if node["kind"] in SCHEMAS_TO_REGISTER]
    for schema in account_schemas:
        await registry.set_schema(name=schema["kind"], schema=NodeSchema(**schema))

    return True


@pytest.fixture
async def first_account(session, register_account_schema):

    obj = await Node.init(session=session, schema="Account")
    await obj.new(session=session, name="First Account", type="GIT")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def second_account(session, register_account_schema):

    obj = await Node.init(session=session, schema="Account")
    await obj.new(session=session, name="Second Account", type="GIT")
    await obj.save(session=session)
    return obj


@pytest.fixture
def dataset01(init_db):
    ds01.load_data()
