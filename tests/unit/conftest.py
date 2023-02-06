import asyncio

import pendulum
import pytest
from neo4j._codec.hydration.v1 import HydrationHandler

import infrahub.config as config
import infrahub.core
from infrahub.core import Registry, registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_default_branch,
    first_time_initialization,
    initialization,
)
from infrahub.core.manager import SchemaManager
from infrahub.core.node import Node
from infrahub.core.schema import (
    GenericSchema,
    GroupSchema,
    NodeSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.utils import delete_all_nodes
from infrahub.database import execute_write_query_async, get_db
from infrahub.message_bus.rpc import InfrahubRpcClientTesting
from infrahub.test_data import dataset01 as ds01


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
async def rpc_client():
    return InfrahubRpcClientTesting()


@pytest.fixture(scope="session")
def neo4j_factory():
    """Return a Hydration Scope from Neo4j used to generate fake
    Node and Relationship object.

    Example:
        fields = [123, {"Person"}, {"name": "Alice", "age": 33}, "123"]
        alice = neo4j_factory.hydrate_node(*fields)
    """
    hydration_scope = HydrationHandler().new_hydration_scope()
    return hydration_scope._graph_hydrator


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
        - branch1 was created at time_m45

    - 2 Cars in Main and 1 in Branch1
        - Car1 was created at time_m60 in main
        - Car2 was created at time_m20 in main
        - Car3 was created at time_m40 in branch1

    - 2 Persons in Main

    """

    time0 = pendulum.now(tz="UTC")
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
        "time_m45": time0.subtract(seconds=45).to_iso8601_string(),
        "time_m50": time0.subtract(seconds=50).to_iso8601_string(),
        "time_m60": time0.subtract(seconds=60).to_iso8601_string(),
    }

    # Create new Branch
    branch1 = Branch(
        name="branch1",
        status="OPEN",
        description="Second Branch",
        is_default=False,
        is_data_only=True,
        branched_from=params["time_m45"],
    )
    await branch1.save(session=session)
    registry.branch[branch1.name] = branch1

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

    CREATE (r1:Relationship { uuid: "r1", name: "car__person"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, status: "active", from: $time_m60 }]->(r1)
    CREATE (c1)-[:IS_RELATED { branch: $main_branch, status: "active", from: $time_m60 }]->(r1)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60, to: $time_m30 }]->(bool_false)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m30 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m20 }]->(bool_false)

    CREATE (r2:Relationship { uuid: "r2", name: "car__person"})
    CREATE (p1)-[:IS_RELATED { branch: $branch1, status: "active", from: $time_m20 }]->(r2)
    CREATE (c2)-[:IS_RELATED { branch: $branch1, status: "active", from: $time_m20 }]->(r2)
    CREATE (r2)-[:IS_PROTECTED {branch: $branch1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (r2)-[:IS_VISIBLE {branch: $branch1, status: "active", from: $time_m20 }]->(bool_true)

    RETURN c1, c2, c3
    """

    await execute_write_query_async(session=session, query=query, params=params)

    return params


@pytest.fixture
async def car_person_schema(session, data_schema):

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
        registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def person_tag_schema(session, data_schema):

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
        registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def all_attribute_types_schema(session, data_schema):

    SCHEMA = {
        "name": "all_attribute_types",
        "kind": "AllAttributeTypes",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "optional": True},
            {"name": "mystring", "kind": "String", "optional": True},
            {"name": "mybool", "kind": "Boolean", "optional": True},
            {"name": "myint", "kind": "Integer", "optional": True},
            {"name": "mylist", "kind": "List", "optional": True},
        ],
    }

    node_schema = NodeSchema(**SCHEMA)
    registry.set_schema(name=node_schema.kind, schema=node_schema)


@pytest.fixture
async def criticality_schema(session, data_schema):

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
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def generic_vehicule_schema(session):

    SCHEMA = {
        "name": "vehicule",
        "kind": "Vehicule",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }

    node = GenericSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def group_on_road_vehicule_schema(session):

    SCHEMA = {
        "name": "on_road",
        "kind": "OnRoad",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }

    node = GroupSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def car_schema(session, generic_vehicule_schema, group_on_road_vehicule_schema, data_schema):

    SCHEMA = {
        "name": "car",
        "kind": "Car",
        "inherit_from": ["Vehicule"],
        "attributes": [
            {"name": "nbr_doors", "kind": "Integer"},
        ],
        "groups": ["OnRoad"],
    }

    node = NodeSchema(**SCHEMA)
    node.extend_with_interface(interface=generic_vehicule_schema)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def motorcycle_schema(session, generic_vehicule_schema, group_on_road_vehicule_schema):

    SCHEMA = {
        "name": "motorcycle",
        "kind": "Motorcycle",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "nbr_seats", "kind": "Integer"},
        ],
        "groups": ["OnRoad"],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def truck_schema(session, generic_vehicule_schema, group_on_road_vehicule_schema):

    SCHEMA = {
        "name": "truck",
        "kind": "Truck",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "nbr_axles", "kind": "Integer"},
        ],
        "groups": ["OnRoad"],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def boat_schema(session, generic_vehicule_schema):

    SCHEMA = {
        "name": "boat",
        "kind": "Boat",
        "inherit_from": ["Vehicule"],
        "attributes": [
            {"name": "has_sails", "kind": "Boolean"},
        ],
        "relationships": [
            {"name": "owners", "peer": "Person", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    node.extend_with_interface(interface=generic_vehicule_schema)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def vehicule_person_schema(session, generic_vehicule_schema, car_schema, boat_schema, motorcycle_schema):

    SCHEMA = {
        "name": "person",
        "kind": "Person",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
        ],
        "relationships": [
            {"name": "vehicules", "peer": "Vehicule", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def fruit_tag_schema(session, data_schema):

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
        registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def data_schema(session):

    SCHEMA = {
        "generics": [
            {
                "name": "data_owner",
                "kind": "DataOwner",
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "description", "kind": "String", "optional": True},
                ],
            },
            {
                "name": "data_source",
                "description": "Any Entities that stores or produces data.",
                "kind": "DataSource",
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "description", "kind": "String", "optional": True},
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.generics:
        registry.set_schema(name=node.kind, schema=node)

    return True


@pytest.fixture
async def reset_registry(session):
    registry.delete_all()


@pytest.fixture
async def empty_database(session):
    await delete_all_nodes(session=session)


@pytest.fixture
async def init_db(empty_database, session):
    await first_time_initialization(session=session)
    await initialization(session=session)


@pytest.fixture
async def default_branch(reset_registry, empty_database, session) -> Branch:
    return await create_default_branch(session=session)


@pytest.fixture
async def register_internal_models_schema(default_branch):

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema, branch=default_branch.name)


@pytest.fixture
async def register_core_models_schema(default_branch, register_internal_models_schema):
    schema = SchemaRoot(**core_models)
    await SchemaManager.register_schema_to_registry(schema=schema, branch=default_branch.name)


@pytest.fixture
async def register_account_schema(session):

    SCHEMAS_TO_REGISTER = ["Account", "AccountToken", "Group"]

    account_schemas = [node for node in core_models["nodes"] if node["kind"] in SCHEMAS_TO_REGISTER]
    for schema in account_schemas:
        registry.set_schema(name=schema["kind"], schema=NodeSchema(**schema))

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
