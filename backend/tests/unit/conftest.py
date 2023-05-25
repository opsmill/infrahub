import asyncio

import pendulum
import pytest
from neo4j import AsyncDriver, AsyncSession
from neo4j._codec.hydration.v1 import HydrationHandler

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_branch,
    create_default_branch,
    create_root_node,
    first_time_initialization,
    initialization,
)
from infrahub.core.manager import SchemaBranch, SchemaManager
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
async def db() -> AsyncDriver:
    driver = await get_db(retry=1)

    yield driver

    await driver.close()


@pytest.fixture
async def session(db: AsyncDriver) -> AsyncSession:
    session = db.session(database=config.SETTINGS.database.database)

    yield session

    await session.close()


@pytest.fixture
async def rpc_client() -> InfrahubRpcClientTesting:
    return InfrahubRpcClientTesting()


@pytest.fixture(params=["main", "branch2"])
async def branch(request, session: AsyncSession, default_branch: Branch):
    if request.param == "main":
        return default_branch
    else:
        return await create_branch(branch_name=str(request.param), session=session)


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
async def simple_dataset_01(session: AsyncSession, empty_database) -> dict:
    await create_root_node(session=session)
    await create_default_branch(session=session)

    params = {
        "branch": "main",
        "time1": pendulum.now(tz="UTC").to_iso8601_string(),
        "time2": pendulum.now(tz="UTC").subtract(seconds=5).to_iso8601_string(),
    }

    query = """
    MATCH (root:Root)

    CREATE (c:Car { uuid: "5ffa45d4" })
    CREATE (c)-[r:IS_PART_OF {branch: $branch, branch_level: 1, from: $time1}]->(root)

    CREATE (at1:Attribute:AttributeLocal { uuid: "ee04c93a", type: "Str", name: "name"})
    CREATE (at2:Attribute:AttributeLocal { uuid: "924786c3", type: "Int", name: "nbr_seats"})
    CREATE (c)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, from: $time1}]->(at1)
    CREATE (c)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, from: $time1}]->(at2)

    CREATE (av11:AttributeValue { uuid: "f6b745c3", value: "accord"})
    CREATE (av12:AttributeValue { uuid: "36100ef6", value: "volt"})
    CREATE (av21:AttributeValue { uuid: "d8d49788",value: 5})
    CREATE (at1)-[:HAS_VALUE {branch: $branch, branch_level: 1, from: $time1, to: $time2}]->(av11)
    CREATE (at1)-[:HAS_VALUE {branch: $branch, branch_level: 1, from: $time2 }]->(av12)
    CREATE (at2)-[:HAS_VALUE {branch: $branch, branch_level: 1, from: $time1 }]->(av21)

    RETURN c, at1, at2
    """

    await execute_write_query_async(session=session, query=query, params=params)

    return params


@pytest.fixture
async def base_dataset_02(session: AsyncSession, default_branch: Branch, car_person_schema) -> dict:
    """Creates a Simple dataset with 2 branches and some changes that can be used for testing.

    To recreate a deterministic timeline, there are 10 timestamps that are being created ahead of time:
      * time0 is now
      * time_m10 is now - 10s
      * time_m20 is now - 20s
      * time_m25 is now - 25s
      * time_m30 is now - 30s
      * time_m35 is now - 35s
      * time_m40 is now - 40s
      * time_m45 is now - 45s
      * time_m50 is now - 50s
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

    # Update Main Branch and Create new Branch1
    default_branch.created_at = params["time_m60"]
    default_branch.branched_from = params["time_m60"]
    await default_branch.save(session=session)

    branch1 = Branch(
        name="branch1",
        status="OPEN",
        description="Second Branch",
        is_default=False,
        is_data_only=True,
        branched_from=params["time_m45"],
        created_at=params["time_m45"],
    )
    await branch1.save(session=session)
    registry.branch[branch1.name] = branch1

    query = """
    MATCH (root:Root)

    CREATE (c1:Node:Car { uuid: "c1", kind: "Car" })
    CREATE (c1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m60, status: "active" }]->(root)

    CREATE (bool_true:Boolean { value: true })
    CREATE (bool_false:Boolean { value: false })

    CREATE (atvf:AttributeValue { value: false })
    CREATE (atvt:AttributeValue { value: true })
    CREATE (atv44:AttributeValue { value: "#444444" })

    CREATE (c1at1:Attribute:AttributeLocal { uuid: "c1at1", type: "Str", name: "name"})
    CREATE (c1at2:Attribute:AttributeLocal { uuid: "c1at2", type: "Int", name: "nbr_seats"})
    CREATE (c1at3:Attribute:AttributeLocal { uuid: "c1at3", type: "Bool", name: "is_electric"})
    CREATE (c1at4:Attribute:AttributeLocal { uuid: "c1at4", type: "Str", name: "color"})
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at1)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at2)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at3)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at4)

    CREATE (c1av11:AttributeValue { value: "accord"})
    CREATE (c1av12:AttributeValue { value: "volt"})
    CREATE (c1av21:AttributeValue { value: 5})
    CREATE (c1av22:AttributeValue { value: 4})

    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m20}]->(c1av11)
    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c1av12)
    CREATE (c1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(c1av21)
    CREATE (c1at2)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(c1av22)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $main_branch,branch_level: 1,  status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_true)
    CREATE (c1at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at3)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(atvt)
    CREATE (c1at3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at4)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(atv44)
    CREATE (c1at4)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at4)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c2:Node:Car { uuid: "c2", kind: "Car" })
    CREATE (c2)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m20, status: "active"}]->(root)

    CREATE (c2at1:Attribute:AttributeLocal { uuid: "c2at1", type: "Str", name: "name"})
    CREATE (c2at2:Attribute:AttributeLocal { uuid: "c2at2", type: "Int", name: "nbr_seats"})
    CREATE (c2at3:Attribute:AttributeLocal { uuid: "c2at3", type: "Bool", name: "is_electric"})
    CREATE (c2at4:Attribute:AttributeLocal { uuid: "c2at4", type: "Str", name: "color"})
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at1)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at2)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at3)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at4)

    CREATE (c2av11:AttributeValue { value: "odyssey" })
    CREATE (c2av21:AttributeValue { value: 8 })

    CREATE (c2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c2av11)
    CREATE (c2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c2av21)
    CREATE (c2at2)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at3)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(atvf)
    CREATE (c2at3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at4)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(atv44)
    CREATE (c2at4)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at4)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c3:Node:Car { uuid: "c3", kind: "Car" })
    CREATE (c3)-[:IS_PART_OF {branch: $branch1, branch_level: 2, from: $time_m40, status: "active"}]->(root)

    CREATE (c3at1:Attribute:AttributeLocal { uuid: "c3at1", type: "Str", name: "name"})
    CREATE (c3at2:Attribute:AttributeLocal { uuid: "c3at2", type: "Int", name: "nbr_seats"})
    CREATE (c3at3:Attribute:AttributeLocal { uuid: "c3at3", type: "Bool", name: "is_electric"})
    CREATE (c3at4:Attribute:AttributeLocal { uuid: "c3at4", type: "Str", name: "color"})
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at1)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at2)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at3)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at4)

    CREATE (c3av11:AttributeValue { uuid: "c3av11", value: "volt"})
    CREATE (c3av21:AttributeValue { uuid: "c3av21", value: 4})

    CREATE (c3at1)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(c3av11)
    CREATE (c3at1)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at1)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at2)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(c3av21)
    CREATE (c3at2)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at2)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at3)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(atvf)
    CREATE (c3at3)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at3)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at4)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(atv44)
    CREATE (c3at4)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at4)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (p1:Node:Person { uuid: "p1", kind: "Person" })
    CREATE (p1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p1at1:Attribute:AttributeLocal { uuid: "p1at1", type: "Str", name: "name"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(p1at1)
    CREATE (p1av11:AttributeValue { uuid: "p1av11", value: "John Doe"})
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p1av11)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p2:Node:Person { uuid: "p2", kind: "Person" })
    CREATE (p2)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p2at1:Attribute:AttributeLocal { uuid: "p2at1", type: "Str", name: "name"})
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(p2at1)
    CREATE (p2av11:AttributeValue { uuid: "p2av11", value: "Jane Doe"})
    CREATE (p2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p2av11)
    CREATE (p2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p3:Node:Person { uuid: "p3", kind: "Person" })
    CREATE (p3)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p3at1:Attribute:AttributeLocal { uuid: "p3at1", type: "Str", name: "name"})
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(p3at1)
    CREATE (p3av11:AttributeValue { uuid: "p3av11", value: "Bill"})
    CREATE (p3at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p3av11)
    CREATE (p3at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p3at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (r1:Relationship { uuid: "r1", name: "car__person"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(r1)
    CREATE (c1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(r1)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m30 }]->(bool_false)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m30 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_false)

    CREATE (r2:Relationship { uuid: "r2", name: "car__person"})
    CREATE (p1)-[:IS_RELATED { branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(r2)
    CREATE (c2)-[:IS_RELATED { branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(r2)
    CREATE (r2)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (r2)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_true)

    RETURN c1, c2, c3
    """

    await execute_write_query_async(session=session, query=query, params=params)

    return params


@pytest.fixture
async def base_dataset_03(session: AsyncSession, default_branch: Branch, person_tag_schema) -> dict:
    """Creates a Dataset with 4 branches, this dataset was initially created to test the diff of Nodes and relationships

    To recreate a deterministic timeline, there are 20 timestamps that are being created ahead of time:
      * time0 is now
      * time_m10 is now - 10s
      * time_m20 is now - 20s
      * time_m25 is now - 25s
      * time_m30 is now - 30s
      * time_m35 is now - 35s
      * time_m40 is now - 40s
      * time_m45 is now - 45s
      * time_m50 is now - 50s
      * time_m60 is now - 60s
      * time_m65 is now - 65s
      * time_m70 is now - 70s
      * time_m75 is now - 75s
      * time_m80 is now - 80s
      * time_m85 is now - 85s
      * time_m90 is now - 90s
      * time_m100 is now - 100s
      * time_m110 is now - 110s
      * time_m115 is now - 115s
      * time_m120 is now - 120s

    - 4 branches : main, branch1, branch2, branch3, branch4
        - branch1 was created at time_m100
        - branch2 was created at time_m90, rebased at m30
        - branch3 was created at time_m70
        - branch4 was created at time_m40
    """

    # ---- Create all timestamps and save them in Params -----------------
    time0 = pendulum.now(tz="UTC")
    params = {
        "main_branch": "main",
        "time0": time0.to_iso8601_string(),
    }

    for cnt in range(1, 30):
        nbr_sec = cnt * 5
        params[f"time_m{nbr_sec}"] = time0.subtract(seconds=nbr_sec).to_iso8601_string()

    # ---- Create all Branches and register them in the Registry -----------------
    # Update Main Branch
    default_branch.created_at = params["time_m120"]
    default_branch.branched_from = params["time_m120"]
    await default_branch.save(session=session)

    branches = (
        ("branch1", "First Branch", "time_m100", "time_m100"),
        ("branch2", "First Branch", "time_m90", "time_m30"),
        ("branch3", "First Branch", "time_m70", "time_m70"),
        ("branch4", "First Branch", "time_m40", "time_m40"),
    )

    for branch_name, description, created_at, branched_from in branches:
        obj = Branch(
            name=branch_name,
            status="OPEN",
            description=description,
            is_default=False,
            is_data_only=True,
            branched_from=params[branched_from],
            created_at=params[created_at],
        )
        await obj.save(session=session)
        registry.branch[obj.name] = obj

        params[branch_name] = branch_name
    # flake8: noqa: F841
    mermaid_graph = """
    gitGraph
        commit id: "CREATE Tag1, Tag2, Tag3, Person1, Person2, Person3 [m120]"
        commit id: "(m110)"
        commit id: "UPDATE P1 Firstname [m100]"
        branch branch1
        checkout main
        commit id: "(m90)"
        branch branch2
        checkout main
        commit id: "UPDATE P1 Firstname [m80]"
        checkout branch2
        commit id: "UPDATE P2 Lastname & Firstname [m80]"
        checkout main
        commit id: "(m70)"
        branch branch3
        checkout main
        commit id: "UPDATE P1 Firstname [m60]"
        commit id: "(m50)"
        commit id: "(m45)"
        branch branch4
        checkout main
        commit id: "UPDATE P1 Firstname [m40]"
        commit id: "(m30)"
        checkout branch2
        commit id: "REBASE [m30]"
        checkout main
        commit id: "(m20)"
        checkout branch2
        commit id: "UPDATE P2 Firstname [m20]"
        checkout main
        commit id: "(m10)"
        commit id: "(m0)"
    """

    query = """
    // Create all branches nodes
    MATCH (root:Root)

    // Create the Boolean nodes for the properties
    CREATE (bool_true:Boolean { value: true })
    CREATE (bool_false:Boolean { value: false })

    // Create the Boolean nodes for the attribute value
    CREATE (atvf:AttributeValue { value: false })
    CREATE (atvt:AttributeValue { value: true })

    // Create a bunch a Attribute Value that can be easily identify and remembered
    CREATE (mon:AttributeValue { value: "monday"})
    CREATE (tue:AttributeValue { value: "tuesday"})
    CREATE (wed:AttributeValue { value: "wednesday"})
    CREATE (thu:AttributeValue { value: "thursday"})
    CREATE (fri:AttributeValue { value: "friday"})
    CREATE (sat:AttributeValue { value: "saturday"})
    CREATE (sun:AttributeValue { value: "sunday"})

    CREATE (jan:AttributeValue { value: "january"})
    CREATE (feb:AttributeValue { value: "february"})
    CREATE (mar:AttributeValue { value: "march"})
    CREATE (apr:AttributeValue { value: "april"})
    CREATE (may:AttributeValue { value: "may"})
    CREATE (june:AttributeValue { value: "june"})
    CREATE (july:AttributeValue { value: "july"})
    CREATE (aug:AttributeValue { value: "august"})
    CREATE (sept:AttributeValue { value: "september"})
    CREATE (oct:AttributeValue { value: "october"})
    CREATE (nov:AttributeValue { value: "november"})
    CREATE (dec:AttributeValue { value: "december"})

    CREATE (blue:AttributeValue { value: "blue"})
    CREATE (red:AttributeValue { value: "red"})
    CREATE (black:AttributeValue { value: "black"})
    CREATE (green:AttributeValue { value: "green"})

    // TAG 1 - BLUE
    CREATE (t1:Node:Tag { uuid: "p1", kind: "Tag" })
    CREATE (t1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (t1at1:Attribute:AttributeLocal { uuid: "t1at1", type: "Str", name: "name"})
    CREATE (t1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(t1at1)

    CREATE (t1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(blue)
    CREATE (t1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (t1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // TAG 2 - RED
    CREATE (t2:Node:Tag { uuid: "t2", kind: "Tag" })
    CREATE (t2)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (t2at1:Attribute:AttributeLocal { uuid: "t2at1", type: "Str", name: "name"})
    CREATE (t2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(t2at1)

    CREATE (t2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(red)
    CREATE (t2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (t2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // TAG 3 - GREEN
    CREATE (t3:Node:Tag { uuid: "t3", kind: "Tag" })
    CREATE (t3)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (t3at1:Attribute:AttributeLocal { uuid: "t3at1", type: "Str", name: "name"})
    CREATE (t3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(t3at1)

    CREATE (t3at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(green)
    CREATE (t3at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (t3at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // PERSON 1
    //  Created in the main branch at m120
    //    tags: Blue, Green
    //    primary Tag: Blue
    //  firstname value in main keeps changing every 20s using the day of the week

    CREATE (p1:Node:Person { uuid: "p1", kind: "Person" })
    CREATE (p1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (p1at1:Attribute:AttributeLocal { uuid: "p1at1", type: "Str", name: "firstname"})
    CREATE (p1at2:Attribute:AttributeLocal { uuid: "p1at2", type: "Str", name: "lastname"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p1at1)
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p1at2)

    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, from: $time_m100 }]->(mon)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m100, from: $time_m80 }]->(tue)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m80, from: $time_m60 }]->(wed)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, from: $time_m40 }]->(thu)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m40 }]->(fri)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    CREATE (p1at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(jan)
    CREATE (p1at2)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p1at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "tags" between Person1 (p1) and Tag Blue (t1) >> relp1t1
    CREATE (relp1t1:Relationship { uuid: "relp1t1", name: "person__tag"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t1)
    CREATE (t1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t1)

    CREATE (relp1t1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp1t1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "tags" between Person1 (p1) and Tag Green (t3) >> relp1t3
    CREATE (relp1t3:Relationship { uuid: "relp1t3", name: "person__tag"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t3)
    CREATE (t3)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t3)

    CREATE (relp1t3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp1t3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "primary_tag" between Person1 (p1) and Tag Blue (t1) >> relp1pri
    CREATE (relp1pri:Relationship { uuid: "relp1pri", name: "person_primary_tag"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1pri)
    CREATE (t1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1pri)

    CREATE (relp1pri)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp1pri)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // PERSON 2
    //  Created in the main branch at m120
    //    tags: Green
    //    primary Tag: None
    //  firstname and lastname values in branch2 changes at m80 before the branch is rebase at m30
    //  firstname value in branch2 changes again at m20 after the branch has been rebased

    CREATE (p2:Node:Person { uuid: "p2", kind: "Person" })
    CREATE (p2)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (p2at1:Attribute:AttributeLocal { uuid: "p1at1", type: "Str", name: "firstname"})
    CREATE (p2at2:Attribute:AttributeLocal { uuid: "p1at2", type: "Str", name: "lastname"})
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p2at1)
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p2at2)

    CREATE (p2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(tue)
    CREATE (p2at1)-[:HAS_VALUE {branch: $branch2, branch_level: 2, status: "active", from: $time_m80, to: $time_m20 }]->(wed)
    CREATE (p2at1)-[:HAS_VALUE {branch: $branch2, branch_level: 2, status: "active", from: $time_m20 }]->(thu)

    CREATE (p2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    CREATE (p2at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(feb)
    CREATE (p2at2)-[:HAS_VALUE {branch: $branch2, branch_level: 2, status: "active", from: $time_m80 }]->(mar)
    CREATE (p2at2)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p2at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "tags" between Person2 (p2) and Tag Green (t3) >> relp2t3
    CREATE (relp2t3:Relationship { uuid: "relp2t3", name: "person__tag"})
    CREATE (p2)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp2t3)
    CREATE (t3)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp2t3)

    CREATE (relp2t3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp2t3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // PERSON 3
    //  Created in the main branch at m120
    //    tags: None
    //    primary Tag: Red

    CREATE (p3:Node:Person { uuid: "p3", kind: "Person" })
    CREATE (p3)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (p3at1:Attribute:AttributeLocal { uuid: "p1at1", type: "Str", name: "firstname"})
    CREATE (p3at2:Attribute:AttributeLocal { uuid: "p1at2", type: "Str", name: "lastname"})
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p3at1)
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p3at2)

    CREATE (p3at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(tue)
    CREATE (p3at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p3at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    CREATE (p3at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(feb)
    CREATE (p3at2)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p3at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "primary_tag" between Person3 (p3) and Tag Red (t2) >> relp3pri
    CREATE (relp3pri:Relationship { uuid: "relp3pri", name: "person_primary_tag"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp3pri)
    CREATE (t1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp3pri)

    CREATE (relp3pri)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp3pri)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    RETURN t1, t2, t3, p1, p2, p3
    """

    await execute_write_query_async(session=session, query=query, params=params)

    return params


@pytest.fixture
async def car_person_schema(session: AsyncSession, default_branch: Branch, data_schema) -> None:
    SCHEMA = {
        "nodes": [
            {
                "name": "car",
                "kind": "Car",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
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
                "display_labels": ["name__value"],
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "Car", "cardinality": "many"}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    for node in schema.nodes:
        registry.set_schema(name=node.kind, schema=node)


@pytest.fixture
async def car_person_manufacturer_schema(session: AsyncSession, data_schema) -> None:
    SCHEMA = {
        "nodes": [
            {
                "name": "car",
                "kind": "Car",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                    {"name": "is_electric", "kind": "Boolean"},
                ],
                "relationships": [
                    {"name": "owner", "peer": "Person", "optional": False, "cardinality": "one"},
                    {"name": "manufacturer", "peer": "Manufacturer", "optional": False, "cardinality": "one"},
                ],
            },
            {
                "name": "person",
                "kind": "Person",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "Car", "cardinality": "many"}],
            },
            {
                "name": "manufacturer",
                "kind": "Manufacturer",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "Car", "cardinality": "many"}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.nodes:
        registry.set_schema(name=node.kind, schema=node)


@pytest.fixture
async def car_person_schema_generics(session: AsyncSession, default_branch: Branch, data_schema) -> None:
    SCHEMA = {
        "generics": [
            {
                "name": "car",
                "kind": "Car",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "Person",
                        "identifier": "person__car",
                        "optional": False,
                        "cardinality": "one",
                    },
                ],
            }
        ],
        "nodes": [
            {
                "name": "electric_car",
                "kind": "ElectricCar",
                "inherit_from": ["Car"],
                "attributes": [
                    {"name": "nbr_engine", "kind": "Number"},
                ],
            },
            {
                "name": "gaz_car",
                "kind": "GazCar",
                "inherit_from": ["Car"],
                "attributes": [
                    {"name": "mpg", "kind": "Number"},
                ],
            },
            {
                "name": "person",
                "kind": "Person",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "Car", "identifier": "person__car", "cardinality": "many"}],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def person_tag_schema(session: AsyncSession, default_branch: Branch, data_schema) -> None:
    SCHEMA = {
        "nodes": [
            {
                "name": "tag",
                "kind": "Tag",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "person",
                "kind": "Person",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "firstname", "kind": "Text"},
                    {"name": "lastname", "kind": "Text"},
                ],
                "relationships": [
                    {"name": "tags", "peer": "Tag", "cardinality": "many"},
                    {"name": "primary_tag", "peer": "Tag", "identifier": "person_primary_tag", "cardinality": "one"},
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def person_john_main(session: AsyncSession, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(session=session, schema="Person", branch=default_branch)
    await person.new(session=session, name="John", height=180)
    await person.save(session=session)

    return person


@pytest.fixture
async def person_jane_main(session: AsyncSession, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(session=session, schema="Person", branch=default_branch)
    await person.new(session=session, name="Jane", height=180)
    await person.save(session=session)

    return person


@pytest.fixture
async def person_jim_main(session: AsyncSession, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(session=session, schema="Person", branch=default_branch)
    await person.new(session=session, name="Jim", height=170)
    await person.save(session=session)

    return person


@pytest.fixture
async def person_albert_main(session: AsyncSession, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(session=session, schema="Person", branch=default_branch)
    await person.new(session=session, name="Albert", height=160)
    await person.save(session=session)

    return person


@pytest.fixture
async def person_alfred_main(session: AsyncSession, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(session=session, schema="Person", branch=default_branch)
    await person.new(session=session, name="Alfred", height=160)
    await person.save(session=session)

    return person


@pytest.fixture
async def car_accord_main(session: AsyncSession, default_branch: Branch, person_john_main: Node) -> Node:
    car = await Node.init(session=session, schema="Car", branch=default_branch)
    await car.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(session=session)

    return car


@pytest.fixture
async def car_volt_main(session: AsyncSession, default_branch: Branch, person_john_main: Node) -> Node:
    car = await Node.init(session=session, schema="Car", branch=default_branch)
    await car.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=person_john_main.id)
    await car.save(session=session)

    return car


@pytest.fixture
async def car_prius_main(session: AsyncSession, default_branch: Branch, person_john_main: Node) -> Node:
    car = await Node.init(session=session, schema="Car", branch=default_branch)
    await car.new(session=session, name="pruis", nbr_seats=5, is_electric=True, owner=person_john_main.id)
    await car.save(session=session)

    return car


@pytest.fixture
async def car_camry_main(session: AsyncSession, default_branch: Branch, person_jane_main: Node) -> Node:
    car = await Node.init(session=session, schema="Car", branch=default_branch)
    await car.new(session=session, name="camry", nbr_seats=5, is_electric=False, owner=person_jane_main.id)
    await car.save(session=session)

    return car


@pytest.fixture
async def car_yaris_main(session: AsyncSession, default_branch: Branch, person_jane_main: Node) -> Node:
    car = await Node.init(session=session, schema="Car", branch=default_branch)
    await car.new(session=session, name="yaris", nbr_seats=4, is_electric=False, owner=person_jane_main.id)
    await car.save(session=session)

    return car


@pytest.fixture
async def tag_blue_main(session: AsyncSession, default_branch: Branch, person_tag_schema) -> Node:
    tag = await Node.init(session=session, schema="Tag", branch=default_branch)
    await tag.new(session=session, name="Blue", description="The Blue tag")
    await tag.save(session=session)

    return tag


@pytest.fixture
async def tag_red_main(session: AsyncSession, default_branch: Branch, person_tag_schema) -> Node:
    tag = await Node.init(session=session, schema="Tag", branch=default_branch)
    await tag.new(session=session, name="Red", description="The Red tag")
    await tag.save(session=session)

    return tag


@pytest.fixture
async def tag_black_main(session: AsyncSession, default_branch: Branch, person_tag_schema) -> Node:
    tag = await Node.init(session=session, schema="Tag", branch=default_branch)
    await tag.new(session=session, name="Black", description="The Black tag")
    await tag.save(session=session)

    return tag


@pytest.fixture
async def person_jack_main(session: AsyncSession, default_branch: Branch, person_tag_schema) -> Node:
    obj = await Node.init(session=session, schema="Person", branch=default_branch)
    await obj.new(session=session, firstname="Jack", lastname="Russell")
    await obj.save(session=session)

    return obj


@pytest.fixture
async def person_jack_primary_tag_main(session: AsyncSession, person_tag_schema, tag_blue_main: Node) -> Node:
    obj = await Node.init(session=session, schema="Person")
    await obj.new(session=session, firstname="Jake", lastname="Russell", primary_tag=tag_blue_main)
    await obj.save(session=session)
    return obj


@pytest.fixture
async def person_jack_tags_main(
    session: AsyncSession, default_branch: Branch, person_tag_schema, tag_blue_main: Node, tag_red_main: Node
) -> Node:
    obj = await Node.init(session=session, schema="Person")
    await obj.new(session=session, firstname="Jake", lastname="Russell", tags=[tag_blue_main, tag_red_main])
    await obj.save(session=session)
    return obj


@pytest.fixture
async def all_attribute_types_schema(session: AsyncSession, default_branch: Branch, data_schema) -> NodeSchema:
    SCHEMA = {
        "name": "all_attribute_types",
        "kind": "AllAttributeTypes",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "optional": True},
            {"name": "mystring", "kind": "Text", "optional": True},
            {"name": "mybool", "kind": "Boolean", "optional": True},
            {"name": "myint", "kind": "Number", "optional": True},
            {"name": "mylist", "kind": "List", "optional": True},
        ],
    }

    node_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=node_schema.kind, schema=node_schema, branch=default_branch.name)

    return node_schema


@pytest.fixture
async def criticality_schema(session: AsyncSession, default_branch: Branch, data_schema) -> NodeSchema:
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "display_labels": ["label__value"],
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "label", "kind": "Text", "optional": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "mylist", "kind": "List", "default_value": ["one", "two"]},
            {"name": "is_true", "kind": "Boolean", "default_value": True},
            {"name": "is_false", "kind": "Boolean", "default_value": False},
            {"name": "description", "kind": "Text", "optional": True},
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node, branch=default_branch.name)

    return node


@pytest.fixture
async def generic_vehicule_schema(session: AsyncSession, default_branch: Branch) -> GenericSchema:
    SCHEMA = {
        "name": "vehicule",
        "kind": "Vehicule",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
        ],
    }

    node = GenericSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node, branch=default_branch.name)

    return node


@pytest.fixture
async def group_on_road_vehicule_schema(session: AsyncSession, default_branch: Branch) -> GroupSchema:
    SCHEMA = {
        "name": "on_road",
        "kind": "OnRoad",
    }

    node = GroupSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node, branch=default_branch.name)

    return node


@pytest.fixture
async def car_schema(
    session: AsyncSession, generic_vehicule_schema, group_on_road_vehicule_schema, data_schema
) -> NodeSchema:
    SCHEMA = {
        "name": "car",
        "kind": "Car",
        "inherit_from": ["Vehicule"],
        "attributes": [
            {"name": "nbr_doors", "kind": "Number"},
        ],
        "groups": ["OnRoad"],
    }

    node = NodeSchema(**SCHEMA)
    node.inherit_from_interface(interface=generic_vehicule_schema)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def motorcycle_schema(
    session: AsyncSession, generic_vehicule_schema, group_on_road_vehicule_schema
) -> NodeSchema:
    SCHEMA = {
        "name": "motorcycle",
        "kind": "Motorcycle",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
            {"name": "nbr_seats", "kind": "Number"},
        ],
        "groups": ["OnRoad"],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def truck_schema(session: AsyncSession, generic_vehicule_schema, group_on_road_vehicule_schema) -> NodeSchema:
    SCHEMA = {
        "name": "truck",
        "kind": "Truck",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
            {"name": "nbr_axles", "kind": "Number"},
        ],
        "groups": ["OnRoad"],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def boat_schema(session: AsyncSession, generic_vehicule_schema) -> NodeSchema:
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
    node.inherit_from_interface(interface=generic_vehicule_schema)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def vehicule_person_schema(
    session: AsyncSession, generic_vehicule_schema, car_schema, boat_schema, motorcycle_schema
) -> NodeSchema:
    SCHEMA = {
        "name": "person",
        "kind": "Person",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "vehicules", "peer": "Vehicule", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.set_schema(name=node.kind, schema=node)

    return node


@pytest.fixture
async def fruit_tag_schema(session: AsyncSession, data_schema) -> SchemaRoot:
    SCHEMA = {
        "nodes": [
            {
                "name": "tag",
                "kind": "Tag",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "color", "kind": "Text", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "fruit",
                "kind": "Fruit",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [{"name": "tags", "peer": "Tag", "cardinality": "many", "optional": False}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    for node in schema.nodes:
        registry.set_schema(name=node.kind, schema=node)

    return schema


@pytest.fixture
async def data_schema(session, default_branch: Branch) -> None:
    SCHEMA = {
        "generics": [
            {
                "name": "data_owner",
                "kind": "DataOwner",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "data_source",
                "description": "Any Entities that stores or produces data.",
                "kind": "DataSource",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def reset_registry(session) -> None:
    registry.delete_all()


@pytest.fixture
async def empty_database(session) -> None:
    await delete_all_nodes(session=session)


@pytest.fixture
async def init_db(empty_database, session) -> None:
    await first_time_initialization(session=session)
    await initialization(session=session)


@pytest.fixture
async def default_branch(reset_registry, empty_database, session) -> Branch:
    await create_root_node(session=session)
    branch = await create_default_branch(session=session)
    registry.schema = SchemaManager()
    return branch


@pytest.fixture
async def register_internal_models_schema(default_branch) -> SchemaBranch:
    schema = SchemaRoot(**internal_schema)
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def register_core_models_schema(default_branch: Branch, register_internal_models_schema) -> SchemaBranch:
    schema = SchemaRoot(**core_models)
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def register_core_schema_db(
    session: AsyncSession, default_branch: Branch, register_core_models_schema
) -> SchemaBranch:
    await registry.schema.load_schema_to_db(schema=register_core_models_schema, branch=default_branch, session=session)
    updated_schema = await registry.schema.load_schema_from_db(session=session, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema)


@pytest.fixture
async def register_account_schema(session) -> None:
    SCHEMAS_TO_REGISTER = ["Account", "AccountToken", "Group"]

    account_schemas = [node for node in core_models["nodes"] if node["kind"] in SCHEMAS_TO_REGISTER]
    for schema in account_schemas:
        registry.set_schema(name=schema["kind"], schema=NodeSchema(**schema))


@pytest.fixture
async def first_account(session: AsyncSession, register_account_schema) -> Node:
    obj = await Node.init(session=session, schema="Account")
    await obj.new(session=session, name="First Account", type="Git")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def second_account(session: AsyncSession, register_account_schema) -> Node:
    obj = await Node.init(session=session, schema="Account")
    await obj.new(session=session, name="Second Account", type="Git")
    await obj.save(session=session)
    return obj


@pytest.fixture
async def repos_in_main(session, register_core_models_schema):
    repo01 = await Node.init(session=session, schema="Repository")
    await repo01.new(session=session, name="repo01", location="git@github.com:user/repo01.git", commit="aaaaaaaaaaa")
    await repo01.save(session=session)

    repo02 = await Node.init(session=session, schema="Repository")
    await repo02.new(session=session, name="repo02", location="git@github.com:user/repo02.git", commit="bbbbbbbbbbb")
    await repo02.save(session=session)

    return {"repo01": repo01, "repo02": repo02}


@pytest.fixture
def dataset01(init_db) -> None:
    ds01.load_data()
