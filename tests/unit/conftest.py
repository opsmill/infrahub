import pendulum
import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_default_branch,
    first_time_initialization,
    initialization,
)
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import NodeSchema, SchemaRoot, core_models, internal_schema
from infrahub.core.node import Node
from infrahub.core.utils import delete_all_nodes
from infrahub.database import execute_write_query
from infrahub.test_data import dataset01 as ds01


@pytest.fixture
def simple_dataset_01():

    delete_all_nodes()
    create_default_branch()

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

    execute_write_query(query, params)


@pytest.fixture
def base_dataset_02():
    """This Dataset includes:
    - 4 timestamps
      * time0 is now
      * time_m20 is now - 20s
      * time_m40 is now - 40s
      * time_m60 is now - 60s

    - 2 branches, main and branch1.
        - branch1  was created at time_m40

    - 2 Cars in Main and 1 in Branch1
        - Car1 was created at time_m60 in main
        - Car2 was created at time_m20 in main
        - Car3 was created at time_m40 in branch1

    - 2 Persons in Main

    """
    delete_all_nodes()
    create_default_branch()

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
    branch1.save()
    registry.branch[branch1.name] = branch1

    params = {
        "main_branch": "main",
        "branch1": "branch1",
        "time0": time0.to_iso8601_string(),
        "time_m20": time0.subtract(seconds=20).to_iso8601_string(),
        "time_m40": time0.subtract(seconds=40).to_iso8601_string(),
        "time_m60": time0.subtract(seconds=60).to_iso8601_string(),
    }

    query = """
    MATCH (b0:Branch { name: $main_branch })
    MATCH (b1:Branch { name: $branch1 })

    CREATE (c1:Car { uuid: "c1" })
    CREATE (c1)-[:IS_PART_OF {from: $time_m60}]->(b0)

    CREATE (bt:Boolean { value: true })
    CREATE (bf:Boolean { value: false })

    CREATE (c1at1:Attribute:AttributeLocal { uuid: "c1at1", type: "Str", name: "name"})
    CREATE (c1at2:Attribute:AttributeLocal { uuid: "c1at2", type: "Int", name: "nbr_seats"})
    CREATE (c1at3:Attribute:AttributeLocal { uuid: "c1at3", type: "Bool", name: "is_electric"})
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at1)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at2)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(c1at3)

    CREATE (c1av11:AttributeValue { uuid: "c1av11", value: "accord"})
    CREATE (c1av12:AttributeValue { uuid: "c1av12", value: "volt"})
    CREATE (c1av21:AttributeValue { uuid: "c1av21", value: 5})
    CREATE (c1av22:AttributeValue { uuid: "c1av22", value: 4})
    CREATE (c1av31:AttributeValue { uuid: "c1av31", value: True })
    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60, to: $time_m20}]->(c1av11)
    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c1av12)
    CREATE (c1at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bf)
    CREATE (c1at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bt)

    CREATE (c1at2)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(c1av21)
    CREATE (c1at2)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m20 }]->(c1av22)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bf)
    CREATE (c1at2)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bt)

    CREATE (c1at3)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60}]->(c1av31)
    CREATE (c1at3)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bf)
    CREATE (c1at3)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bt)

    CREATE (c2:Car { uuid: "c2" })
    CREATE (c2)-[:IS_PART_OF {from: $time_m20}]->(b0)

    CREATE (c2at1:Attribute:AttributeLocal { uuid: "c2at1", type: "Str", name: "name"})
    CREATE (c2at2:Attribute:AttributeLocal { uuid: "c2at2", type: "Int", name: "nbr_seats"})
    CREATE (c2at3:Attribute:AttributeLocal { uuid: "c2at3", type: "Bool", name: "is_electric"})
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at1)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at2)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m20}]->(c2at3)

    CREATE (c2av11:AttributeValue { uuid: "c2av11", value: "odyssey"})
    CREATE (c2av21:AttributeValue { uuid: "c2av21", value: 8})
    CREATE (c2av31:AttributeValue { uuid: "c2av31", value: False})
    CREATE (c2at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c2av11)
    CREATE (c2at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bf)
    CREATE (c2at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bt)

    CREATE (c2at2)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c2av21)
    CREATE (c2at2)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bf)
    CREATE (c2at2)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bt)

    CREATE (c2at3)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m20 }]->(c2av31)
    CREATE (c2at3)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m20 }]->(bf)
    CREATE (c2at3)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m20 }]->(bt)

    CREATE (c3:Car { uuid: "c3" })
    CREATE (c3)-[:IS_PART_OF {from: $time_m40}]->(b1)

    CREATE (c3at1:Attribute:AttributeLocal { uuid: "c3at1", type: "Str", name: "name"})
    CREATE (c3at2:Attribute:AttributeLocal { uuid: "c3at2", type: "Int", name: "nbr_seats"})
    CREATE (c3at3:Attribute:AttributeLocal { uuid: "c3at3", type: "Bool", name: "is_electric"})
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at1)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at2)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, status: "active", from: $time_m40}]->(c3at3)

    CREATE (c3av11:AttributeValue { uuid: "c3av11", value: "volt"})
    CREATE (c3av21:AttributeValue { uuid: "c3av21", value: 4})
    CREATE (c3av31:AttributeValue { uuid: "c3av31", value: False})
    CREATE (c3at1)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(c3av11)
    CREATE (c3at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m40 }]->(bf)
    CREATE (c3at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m40 }]->(bt)

    CREATE (c3at2)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(c3av21)
    CREATE (c3at2)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m40 }]->(bf)
    CREATE (c3at2)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m40 }]->(bt)

    CREATE (c3at3)-[:HAS_VALUE {branch: $branch1, status: "active", from: $time_m40 }]->(c3av31)
    CREATE (c3at3)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m40 }]->(bf)
    CREATE (c3at3)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m40 }]->(bt)

    CREATE (p1:Person { uuid: "p1" })
    CREATE (p1)-[:IS_PART_OF {from: $time_m60}]->(b0)
    CREATE (p1at1:Attribute:AttributeLocal { uuid: "p1at1", type: "Str", name: "name"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(p1at1)
    CREATE (p1av11:AttributeValue { uuid: "p1av11", value: "John Doe"})
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(p1av11)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bf)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bt)

    CREATE (p2:Person { uuid: "p2" })
    CREATE (p2)-[:IS_PART_OF {from: $time_m60}]->(b0)
    CREATE (p2at1:Attribute:AttributeLocal { uuid: "p2at1", type: "Str", name: "name"})
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $main_branch, status: "active", from: $time_m60}]->(p2at1)
    CREATE (p2av11:AttributeValue { uuid: "p2av11", value: "Jane Doe"})
    CREATE (p2at1)-[:HAS_VALUE {branch: $main_branch, status: "active", from: $time_m60 }]->(p2av11)
    CREATE (p2at1)-[:IS_PROTECTED {branch: $main_branch, status: "active", from: $time_m60 }]->(bf)
    CREATE (p2at1)-[:IS_VISIBLE {branch: $main_branch, status: "active", from: $time_m60 }]->(bt)

    CREATE (r1:Relationship { uuid: "r1", type: "PERSON_CAR"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, status: "active", from: $time_m60 }]->(r1)
    CREATE (c1)-[:IS_RELATED { branch: $main_branch, status: "active", from: $time_m60 }]->(r1)

    CREATE (r2:Relationship { uuid: "r2", type: "PERSON_CAR"})
    CREATE (p1)-[:IS_RELATED { branch: $branch1, status: "active", from: $time_m20 }]->(r2)
    CREATE (c2)-[:IS_RELATED { branch: $branch1, status: "active", from: $time_m20 }]->(r2)

    RETURN c1, c2, c3
    """

    execute_write_query(query, params)

    return params


@pytest.fixture
def car_person_schema():

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
                    {"name": "height", "kind": "Integer"},
                ],
                "relationships": [{"name": "cars", "peer": "Car", "cardinality": "many"}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.nodes:
        registry.set_schema(node.kind, node)

    return True


@pytest.fixture
def person_tag_schema():

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
        registry.set_schema(node.kind, node)

    return True


@pytest.fixture
def criticality_schema():

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
    registry.set_schema(node.kind, node)

    return node


@pytest.fixture
def fruit_tag_schema():

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
        registry.set_schema(node.kind, node)

    return True


@pytest.fixture
def init_db():
    delete_all_nodes()
    first_time_initialization()
    initialization()


@pytest.fixture()
def default_branch():
    delete_all_nodes()
    return create_default_branch()


@pytest.fixture()
def register_core_models_schema():

    schema = SchemaRoot(**internal_schema)
    SchemaManager.register_schema_to_registry(schema)

    schema = SchemaRoot(**core_models)
    SchemaManager.register_schema_to_registry(schema)


@pytest.fixture()
def register_account_schema():

    SCHEMAS_TO_REGISTER = ["Account", "AccountToken", "Group"]

    account_schemas = [node for node in core_models["nodes"] if node["kind"] in SCHEMAS_TO_REGISTER]
    for schema in account_schemas:
        registry.set_schema(schema["kind"], NodeSchema(**schema))

    return True


@pytest.fixture()
def first_account(register_account_schema):
    return Node("Account").new(name="First Account", type="USER").save()


@pytest.fixture()
def second_account(register_account_schema):
    return Node("Account").new(name="Second Account", type="GIT").save()


@pytest.fixture
def dataset01(init_db):
    ds01.load_data()
