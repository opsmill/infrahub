import os
import shutil
from itertools import islice
from typing import Any, Dict

import pendulum
import pytest
from infrahub_sdk import UUIDT
from neo4j._codec.hydration.v1 import HydrationHandler
from pytest_httpx import HTTPXMock

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, InfrahubKind
from infrahub.core.initialization import (
    create_branch,
    create_default_branch,
    create_root_node,
    first_time_initialization,
    initialization,
)
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.core.node.resource_manager import CorePrefixGlobalPool, CorePrefixPool
from infrahub.core.schema import (
    GenericSchema,
    NodeSchema,
    SchemaRoot,
    core_models,
)
from infrahub.core.schema_manager import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import build_component_registry
from infrahub.git import InfrahubRepository
from infrahub.test_data import dataset01 as ds01
from tests.helpers.file_repo import FileRepo


@pytest.fixture(scope="module", autouse=True)
def load_component_dependency_registry():
    build_component_registry()


@pytest.fixture(params=["main", "branch2"])
async def branch(request, db: InfrahubDatabase, default_branch: Branch):
    if request.param == "main":
        return default_branch

    return await create_branch(branch_name=str(request.param), db=db)


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
def git_sources_dir(default_branch, tmp_path) -> str:
    source_dir = os.path.join(str(tmp_path), "sources")

    os.mkdir(source_dir)

    return source_dir


@pytest.fixture
def git_repos_dir(tmp_path) -> str:
    repos_dir = os.path.join(str(tmp_path), "repositories")

    os.mkdir(repos_dir)

    config.SETTINGS.git.repositories_directory = repos_dir

    return repos_dir


@pytest.fixture
async def git_fixture_repo(git_sources_dir, git_repos_dir) -> InfrahubRepository:
    FileRepo(name="test_base", sources_directory=git_sources_dir)

    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="test_basename",
        location=f"{git_sources_dir}/test_base",
    )

    await repo.create_branch_in_git(branch_name="main", branch_id="8808dcea-f7b4-4f5a-b5e9-a0605d4c11ba")

    return repo


@pytest.fixture
def s3_storage_bucket() -> str:
    bucket_name = "mocked"
    config.SETTINGS.storage.driver = config.StorageDriver.InfrahubS3ObjectStorage
    config.SETTINGS.storage.s3 = config.S3StorageSettings(
        AWS_S3_BUCKET_NAME=bucket_name,
        AWS_ACCESS_KEY_ID="some_id",
        AWS_SECRET_ACCESS_KEY="secret_key",
        AWS_S3_ENDPOINT_URL="storage.googleapis.com",
    )
    return config.SETTINGS.storage.s3.endpoint_url


@pytest.fixture
def file1_in_storage(local_storage_dir, helper) -> str:
    fixture_dir = helper.get_fixtures_dir()
    file1_identifier = str(UUIDT())

    files_dir = os.path.join(fixture_dir, "schemas")

    filenames = [item.name for item in os.scandir(files_dir) if item.is_file()]
    shutil.copyfile(os.path.join(files_dir, filenames[0]), os.path.join(local_storage_dir, file1_identifier))

    return file1_identifier


@pytest.fixture
async def simple_dataset_01(db: InfrahubDatabase, empty_database) -> dict:
    await create_default_branch(db=db)

    params = {
        "branch": "main",
        "time1": pendulum.now(tz="UTC").to_iso8601_string(),
        "time2": pendulum.now(tz="UTC").subtract(seconds=5).to_iso8601_string(),
    }

    query = """
    MATCH (root:Root)

    CREATE (c:Car { uuid: "5ffa45d4" })
    CREATE (c)-[r:IS_PART_OF {branch: $branch, branch_level: 1, from: $time1}]->(root)

    CREATE (at1:Attribute { uuid: "ee04c93a", name: "name"})
    CREATE (at2:Attribute { uuid: "924786c3", name: "nbr_seats"})
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

    await db.execute_query(query=query, params=params)

    return params


@pytest.fixture
async def base_dataset_02(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> dict:
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
    await default_branch.save(db=db)

    branch1 = Branch(
        name="branch1",
        status="OPEN",
        description="Second Branch",
        is_default=False,
        sync_with_git=False,
        branched_from=params["time_m45"],
        created_at=params["time_m45"],
    )
    await branch1.save(db=db)
    registry.branch[branch1.name] = branch1
    schema_branch1 = registry.schema.get_schema_branch(name=default_branch.name).duplicate(name=branch1.name)
    registry.schema.set_schema_branch(name=branch1.name, schema=schema_branch1)

    query = """
    MATCH (root:Root)

    CREATE (c1:Node:TestCar { uuid: "c1", namespace: "Test", kind: "TestCar", branch_support: "aware" })
    CREATE (c1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m60, status: "active" }]->(root)

    CREATE (bool_true:Boolean { value: true })
    CREATE (bool_false:Boolean { value: false })

    CREATE (atvf:AttributeValue { value: false, is_default: false  })
    CREATE (atvt:AttributeValue { value: true, is_default: false  })
    CREATE (atv44:AttributeValue { value: "#444444", is_default: false  })

    CREATE (c1at1:Attribute { uuid: "c1at1", name: "name", branch_support: "aware"})
    CREATE (c1at2:Attribute { uuid: "c1at2", name: "nbr_seats", branch_support: "aware"})
    CREATE (c1at3:Attribute { uuid: "c1at3", name: "is_electric", branch_support: "aware"})
    CREATE (c1at4:Attribute { uuid: "c1at4", name: "color", branch_support: "aware"})
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at1)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at2)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at3)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at4)

    CREATE (c1av11:AttributeValue { value: "accord", is_default: false })
    CREATE (c1av12:AttributeValue { value: "volt", is_default: false })
    CREATE (c1av21:AttributeValue { value: 5, is_default: false })
    CREATE (c1av22:AttributeValue { value: 4, is_default: false })

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

    CREATE (c2:Node:TestCar { uuid: "c2", namespace: "Test", kind: "TestCar", branch_support: "aware" })
    CREATE (c2)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m20, status: "active"}]->(root)

    CREATE (c2at1:Attribute { uuid: "c2at1", name: "name", branch_support: "aware"})
    CREATE (c2at2:Attribute { uuid: "c2at2", name: "nbr_seats", branch_support: "aware"})
    CREATE (c2at3:Attribute { uuid: "c2at3", name: "is_electric", branch_support: "aware"})
    CREATE (c2at4:Attribute { uuid: "c2at4", name: "color", branch_support: "aware"})
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at1)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at2)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at3)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at4)

    CREATE (c2av11:AttributeValue { value: "odyssey", is_default: false })
    CREATE (c2av21:AttributeValue { value: 8, is_default: false })

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

    CREATE (c3:Node:TestCar { uuid: "c3", namespace: "Test", kind: "TestCar", branch_support: "aware" })
    CREATE (c3)-[:IS_PART_OF {branch: $branch1, branch_level: 2, from: $time_m40, status: "active"}]->(root)

    CREATE (c3at1:Attribute { uuid: "c3at1", name: "name", branch_support: "aware"})
    CREATE (c3at2:Attribute { uuid: "c3at2", name: "nbr_seats", branch_support: "aware"})
    CREATE (c3at3:Attribute { uuid: "c3at3", name: "is_electric", branch_support: "aware"})
    CREATE (c3at4:Attribute { uuid: "c3at4", name: "color", branch_support: "aware"})
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at1)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at2)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at3)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at4)

    CREATE (c3av11:AttributeValue { value: "volt", is_default: false })
    CREATE (c3av21:AttributeValue { value: 4, is_default: false })

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

    CREATE (p1:Node:TestPerson { uuid: "p1", namespace: "Test", kind: "TestPerson", branch_support: "aware" })
    CREATE (p1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p1at1:Attribute { uuid: "p1at1", name: "name", branch_support: "aware"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(p1at1)
    CREATE (p1av11:AttributeValue { value: "John Doe", is_default: false })
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p1av11)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p2:Node:TestPerson { uuid: "p2", namespace: "Test", kind: "TestPerson", branch_support: "aware" })
    CREATE (p2)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p2at1:Attribute { uuid: "p2at1", name: "name", branch_support: "aware"})
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(p2at1)
    CREATE (p2av11:AttributeValue { value: "Jane Doe", is_default: false })
    CREATE (p2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p2av11)
    CREATE (p2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p3:Node:TestPerson { uuid: "p3", namespace: "Test", kind: "TestPerson", branch_support: "aware" })
    CREATE (p3)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p3at1:Attribute { uuid: "p3at1", name: "name", branch_support: "aware"})
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(p3at1)
    CREATE (p3av11:AttributeValue { value: "Bill", is_default: false })
    CREATE (p3at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p3av11)
    CREATE (p3at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p3at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (r1:Relationship { uuid: "r1", name: "testcar__testperson", branch_support: "aware"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(r1)
    CREATE (c1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(r1)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m30 }]->(bool_false)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m30 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_false)

    CREATE (r2:Relationship { uuid: "r2", name: "testcar__testperson", branch_support: "aware"})
    CREATE (p1)-[:IS_RELATED { branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(r2)
    CREATE (c2)-[:IS_RELATED { branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(r2)
    CREATE (r2)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (r2)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_true)

    RETURN c1, c2, c3
    """

    await db.execute_query(query=query, params=params)

    return params


@pytest.fixture
async def base_dataset_12(db: InfrahubDatabase, default_branch: Branch, car_person_schema_global) -> dict:
    """Creates a Simple dataset with 2 branches and some changes that can be used for testing.
    This dataset is based on base_dataset_02 but it uses a different schema with person includes the global branch as well

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
        "global_branch": GLOBAL_BRANCH_NAME,
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
    await default_branch.save(db=db)

    branch1 = Branch(
        name="branch1",
        status="OPEN",
        description="Second Branch",
        is_default=False,
        sync_with_git=False,
        branched_from=params["time_m45"],
        created_at=params["time_m45"],
    )
    await branch1.save(db=db)
    registry.branch[branch1.name] = branch1

    query = """
    MATCH (root:Root)

    CREATE (c1:Node:TestCar { uuid: "c1", namespace: "Test", kind: "TestCar", branch_support: "aware" })
    CREATE (c1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m60, status: "active" }]->(root)

    CREATE (bool_true:Boolean { value: true })
    CREATE (bool_false:Boolean { value: false })

    CREATE (atvf:AttributeValue { value: false, is_default: false  })
    CREATE (atvt:AttributeValue { value: true, is_default: false  })
    CREATE (atv44:AttributeValue { value: "#444444", is_default: false  })

    CREATE (c1at1:Attribute { uuid: "c1at1", name: "name", branch_support: "aware"})
    CREATE (c1at2:Attribute { uuid: "c1at2", name: "nbr_seats", branch_support: "agnostic"})
    CREATE (c1at3:Attribute { uuid: "c1at3", name: "is_electric", branch_support: "aware"})
    CREATE (c1at4:Attribute { uuid: "c1at4", name: "color", branch_support: "aware"})
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at1)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at2)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at3)
    CREATE (c1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(c1at4)

    CREATE (c1av11:AttributeValue { value: "accord", is_default: false })
    CREATE (c1av12:AttributeValue { value: "volt", is_default: false })
    CREATE (c1av21:AttributeValue { value: 5, is_default: false })
    CREATE (c1av22:AttributeValue { value: 4, is_default: false })

    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m20}]->(c1av11)
    CREATE (c1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c1av12)
    CREATE (c1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at2)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m20 }]->(c1av21)
    CREATE (c1at2)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c1av22)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $global_branch,branch_level: 1,  status: "active", from: $time_m60, to: $time_m20 }]->(bool_false)
    CREATE (c1at2)-[:IS_PROTECTED {branch: $global_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)
    CREATE (c1at2)-[:IS_VISIBLE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at3)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(atvt)
    CREATE (c1at3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c1at4)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60}]->(atv44)
    CREATE (c1at4)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (c1at4)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (c2:Node:TestCar { uuid: "c2", namespace: "Test", kind: "TestCar", branch_support: "aware" })
    CREATE (c2)-[:IS_PART_OF {branch: $main_branch, branch_level: 1, from: $time_m20, status: "active"}]->(root)

    CREATE (c2at1:Attribute { uuid: "c2at1", name: "name", branch_support: "aware"})
    CREATE (c2at2:Attribute { uuid: "c2at2", name: "nbr_seats", branch_support: "agnostic"})
    CREATE (c2at3:Attribute { uuid: "c2at3", name: "is_electric", branch_support: "aware"})
    CREATE (c2at4:Attribute { uuid: "c2at4", name: "color", branch_support: "aware"})
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at1)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at2)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at3)
    CREATE (c2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20}]->(c2at4)

    CREATE (c2av11:AttributeValue { value: "odyssey", is_default: false })
    CREATE (c2av21:AttributeValue { value: 8, is_default: false })

    CREATE (c2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c2av11)
    CREATE (c2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at2)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m20 }]->(c2av21)
    CREATE (c2at2)-[:IS_PROTECTED {branch: $global_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at2)-[:IS_VISIBLE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at3)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(atvf)
    CREATE (c2at3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c2at4)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(atv44)
    CREATE (c2at4)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (c2at4)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m20 }]->(bool_true)

    CREATE (c3:Node:TestCar { uuid: "c3", namespace: "Test", kind: "TestCar", branch_support: "aware" })
    CREATE (c3)-[:IS_PART_OF {branch: $branch1, branch_level: 2, from: $time_m40, status: "active"}]->(root)

    CREATE (c3at1:Attribute { uuid: "c3at1", name: "name", branch_support: "aware"})
    CREATE (c3at2:Attribute { uuid: "c3at2", name: "nbr_seats", branch_support: "agnostic"})
    CREATE (c3at3:Attribute { uuid: "c3at3", name: "is_electric", branch_support: "aware"})
    CREATE (c3at4:Attribute { uuid: "c3at4", name: "color", branch_support: "aware"})
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at1)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m40}]->(c3at2)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at3)
    CREATE (c3)-[:HAS_ATTRIBUTE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40}]->(c3at4)

    CREATE (c3av11:AttributeValue { value: "volt", is_default: false })
    CREATE (c3av21:AttributeValue { value: 4, is_default: false })

    CREATE (c3at1)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(c3av11)
    CREATE (c3at1)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at1)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at2)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m40 }]->(c3av21)
    CREATE (c3at2)-[:IS_PROTECTED {branch: $global_branch, branch_level: 1, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at2)-[:IS_VISIBLE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at3)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(atvf)
    CREATE (c3at3)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at3)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (c3at4)-[:HAS_VALUE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(atv44)
    CREATE (c3at4)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_false)
    CREATE (c3at4)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m40 }]->(bool_true)

    CREATE (p1:Node:TestPerson { uuid: "p1", namespace: "Test", kind: "TestPerson", branch_support: "agnostic" })
    CREATE (p1)-[:IS_PART_OF { branch: $global_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p1at1:Attribute { uuid: "p1at1", name: "name", branch_support: "agnostic"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60}]->(p1at1)
    CREATE (p1av11:AttributeValue { value: "John Doe", is_default: false })
    CREATE (p1at1)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p1av11)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p2:Node:TestPerson { uuid: "p2", namespace: "Test", kind: "TestPerson", branch_support: "agnostic" })
    CREATE (p2)-[:IS_PART_OF {branch: $global_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p2at1:Attribute { uuid: "p2at1", name: "name", branch_support: "agnostic"})
    CREATE (p2)-[:HAS_ATTRIBUTE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60}]->(p2at1)
    CREATE (p2av11:AttributeValue { value: "Jane Doe", is_default: false })
    CREATE (p2at1)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p2av11)
    CREATE (p2at1)-[:IS_PROTECTED {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p2at1)-[:IS_VISIBLE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (p3:Node:TestPerson { uuid: "p3", namespace: "Test", kind: "TestPerson", branch_support: "agnostic" })
    CREATE (p3)-[:IS_PART_OF {branch: $global_branch, branch_level: 1, from: $time_m60, status: "active"}]->(root)
    CREATE (p3at1:Attribute { uuid: "p3at1", name: "name", branch_support: "agnostic"})
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60}]->(p3at1)
    CREATE (p3av11:AttributeValue { value: "Bill", is_default: false })
    CREATE (p3at1)-[:HAS_VALUE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(p3av11)
    CREATE (p3at1)-[:IS_PROTECTED {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_false)
    CREATE (p3at1)-[:IS_VISIBLE {branch: $global_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)

    CREATE (r1:Relationship { uuid: "r1", name: "testcar__testperson", branch_support: "agnostic"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(r1)
    CREATE (c1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(r1)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m30 }]->(bool_false)
    CREATE (r1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m30 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60 }]->(bool_true)
    CREATE (r1)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_false)

    CREATE (r2:Relationship { uuid: "r2", name: "testcar__testperson", branch_support: "agnostic"})
    CREATE (p1)-[:IS_RELATED { branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(r2)
    CREATE (c2)-[:IS_RELATED { branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(r2)
    CREATE (r2)-[:IS_PROTECTED {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_false)
    CREATE (r2)-[:IS_VISIBLE {branch: $branch1, branch_level: 2, status: "active", from: $time_m20 }]->(bool_true)

    RETURN c1, c2, c3
    """

    await db.execute_query(query=query, params=params)

    return params


@pytest.fixture
async def base_dataset_03(db: InfrahubDatabase, default_branch: Branch, person_tag_schema) -> dict:
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
    await default_branch.save(db=db)

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
            sync_with_git=False,
            branched_from=params[branched_from],
            created_at=params[created_at],
        )
        await obj.save(db=db)
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

    query1 = """
    // Create all branches nodes
    MATCH (root:Root)

    // Create the Boolean nodes for the properties
    CREATE (bool_true:Boolean { value: true })
    CREATE (bool_false:Boolean { value: false })

    // Create the Boolean nodes for the attribute value
    CREATE (atvf:AttributeValue { value: false, is_default: false })
    CREATE (atvt:AttributeValue { value: true, is_default: false })

    // Create a bunch a Attribute Value that can be easily identify and remembered
    CREATE (mon:AttributeValue { value: "monday", is_default: false })
    CREATE (tue:AttributeValue { value: "tuesday", is_default: false })
    CREATE (wed:AttributeValue { value: "wednesday", is_default: false })
    CREATE (thu:AttributeValue { value: "thursday", is_default: false })
    CREATE (fri:AttributeValue { value: "friday", is_default: false })
    CREATE (sat:AttributeValue { value: "saturday", is_default: false })
    CREATE (sun:AttributeValue { value: "sunday", is_default: false })

    CREATE (jan:AttributeValue { value: "january", is_default: false })
    CREATE (feb:AttributeValue { value: "february", is_default: false })
    CREATE (mar:AttributeValue { value: "march", is_default: false })
    CREATE (apr:AttributeValue { value: "april", is_default: false })
    CREATE (may:AttributeValue { value: "may", is_default: false })
    CREATE (june:AttributeValue { value: "june", is_default: false })
    CREATE (july:AttributeValue { value: "july", is_default: false })
    CREATE (aug:AttributeValue { value: "august", is_default: false })
    CREATE (sept:AttributeValue { value: "september", is_default: false })
    CREATE (oct:AttributeValue { value: "october", is_default: false })
    CREATE (nov:AttributeValue { value: "november", is_default: false })
    CREATE (dec:AttributeValue { value: "december", is_default: false })

    CREATE (blue:AttributeValue { value: "blue", is_default: false })
    CREATE (red:AttributeValue { value: "red", is_default: false })
    CREATE (black:AttributeValue { value: "black", is_default: false })
    CREATE (green:AttributeValue { value: "green", is_default: false })

    // TAG 1 - BLUE
    CREATE (t1:Node:Tag { uuid: "t1", kind: "Tag", branch_support: "aware"})
    CREATE (t1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (t1at1:Attribute { uuid: "t1at1", name: "name", branch_support: "aware"})
    CREATE (t1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(t1at1)

    CREATE (t1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(blue)
    CREATE (t1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (t1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // TAG 2 - RED
    CREATE (t2:Node:Tag { uuid: "t2", kind: "Tag", branch_support: "aware" })
    CREATE (t2)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (t2at1:Attribute { uuid: "t2at1", name: "name", branch_support: "aware"})
    CREATE (t2)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(t2at1)

    CREATE (t2at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(red)
    CREATE (t2at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (t2at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // TAG 3 - GREEN
    CREATE (t3:Node:Tag { uuid: "t3", kind: "Tag", branch_support: "aware" })
    CREATE (t3)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (t3at1:Attribute { uuid: "t3at1", name: "name", branch_support: "aware"})
    CREATE (t3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(t3at1)

    CREATE (t3at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(green)
    CREATE (t3at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (t3at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    RETURN t1, t2, t3
    """

    query_prefix = """
    MATCH (root:Root)

    MATCH (t1:Tag {uuid: "t1"})
    MATCH (t2:Tag {uuid: "t2"})
    MATCH (t3:Tag {uuid: "t3"})

    // Create the Boolean nodes for the properties
    MERGE (bool_true:Boolean { value: true })
    MERGE (bool_false:Boolean { value: false })

    // Create the Boolean nodes for the attribute value
    MERGE (atvf:AttributeValue { value: false, is_default: false  })
    MERGE (atvt:AttributeValue { value: true, is_default: false  })

    // Create a bunch a Attribute Value that can be easily identify and remembered
    MERGE (mon:AttributeValue { value: "monday", is_default: false })
    MERGE (tue:AttributeValue { value: "tuesday", is_default: false })
    MERGE (wed:AttributeValue { value: "wednesday", is_default: false })
    MERGE (thu:AttributeValue { value: "thursday", is_default: false })
    MERGE (fri:AttributeValue { value: "friday", is_default: false })
    MERGE (sat:AttributeValue { value: "saturday", is_default: false })
    MERGE (sun:AttributeValue { value: "sunday", is_default: false })

    MERGE (jan:AttributeValue { value: "january", is_default: false })
    MERGE (feb:AttributeValue { value: "february", is_default: false })
    MERGE (mar:AttributeValue { value: "march", is_default: false })
    MERGE (apr:AttributeValue { value: "april", is_default: false })
    MERGE (may:AttributeValue { value: "may", is_default: false })
    MERGE (june:AttributeValue { value: "june", is_default: false })
    MERGE (july:AttributeValue { value: "july", is_default: false })
    MERGE (aug:AttributeValue { value: "august", is_default: false })
    MERGE (sept:AttributeValue { value: "september", is_default: false })
    MERGE (oct:AttributeValue { value: "october", is_default: false })
    MERGE (nov:AttributeValue { value: "november", is_default: false })
    MERGE (dec:AttributeValue { value: "december", is_default: false })
    """

    query2 = """
    // PERSON 1
    //  Created in the main branch at m120
    //    tags: Blue, Green
    //    primary Tag: Blue
    //  firstname value in main keeps changing every 20s using the day of the week

    CREATE (p1:Node:Person { uuid: "p1", kind: "Person", branch_support: "aware" })
    CREATE (p1)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (p1at1:Attribute { uuid: "p1at1", name: "firstname", branch_support: "aware"})
    CREATE (p1at2:Attribute { uuid: "p1at2", name: "lastname", branch_support: "aware"})
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p1at1)
    CREATE (p1)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p1at2)

    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m100 }]->(mon)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m100, to: $time_m80 }]->(tue)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m80, to: $time_m60 }]->(wed)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m60, to: $time_m40 }]->(thu)
    CREATE (p1at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m40 }]->(fri)
    CREATE (p1at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p1at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    CREATE (p1at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(jan)
    CREATE (p1at2)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p1at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "tags" between Person1 (p1) and Tag Blue (t1) >> relp1t1
    CREATE (relp1t1:Relationship { uuid: "relp1t1", name: "person__tag", branch_support: "aware"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t1)
    CREATE (t1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t1)

    CREATE (relp1t1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp1t1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "tags" between Person1 (p1) and Tag Green (t3) >> relp1t3
    CREATE (relp1t3:Relationship { uuid: "relp1t3", name: "person__tag", branch_support: "aware"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t3)
    CREATE (t3)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1t3)

    CREATE (relp1t3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp1t3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "primary_tag" between Person1 (p1) and Tag Blue (t1) >> relp1pri
    CREATE (relp1pri:Relationship { uuid: "relp1pri", name: "person_primary_tag", branch_support: "aware"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1pri)
    CREATE (t1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp1pri)

    CREATE (relp1pri)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp1pri)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)
    """

    query3 = """
    // PERSON 2
    //  Created in the main branch at m120
    //    tags: Green
    //    primary Tag: None
    //  firstname and lastname values in branch2 changes at m80 before the branch is rebase at m30
    //  firstname value in branch2 changes again at m20 after the branch has been rebased

    CREATE (p2:Node:Person { uuid: "p2", kind: "Person", branch_support: "aware" })
    CREATE (p2)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (p2at1:Attribute { uuid: "p1at1", name: "firstname", branch_support: "aware"})
    CREATE (p2at2:Attribute { uuid: "p1at2", name: "lastname", branch_support: "aware"})
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
    CREATE (relp2t3:Relationship { uuid: "relp2t3", name: "person__tag", branch_support: "aware"})
    CREATE (p2)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp2t3)
    CREATE (t3)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp2t3)

    CREATE (relp2t3)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp2t3)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)
    """

    query4 = """
    // PERSON 3
    //  Created in the main branch at m120
    //    tags: None
    //    primary Tag: Red

    CREATE (p3:Node:Person { uuid: "p3", kind: "Person", branch_support: "aware" })
    CREATE (p3)-[:IS_PART_OF { branch: $main_branch, branch_level: 1, from: $time_m120, status: "active" }]->(root)

    CREATE (p3at1:Attribute { uuid: "p1at1", name: "firstname", branch_support: "aware"})
    CREATE (p3at2:Attribute { uuid: "p1at2", name: "lastname", branch_support: "aware"})
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p3at1)
    CREATE (p3)-[:HAS_ATTRIBUTE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120}]->(p3at2)

    CREATE (p3at1)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120, to: $time_m20}]->(tue)
    CREATE (p3at1)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p3at1)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    CREATE (p3at2)-[:HAS_VALUE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(feb)
    CREATE (p3at2)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (p3at2)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    // Relationship for "primary_tag" between Person3 (p3) and Tag Red (t2) >> relp3pri
    CREATE (relp3pri:Relationship { uuid: "relp3pri", name: "person_primary_tag", branch_support: "aware"})
    CREATE (p1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp3pri)
    CREATE (t1)-[:IS_RELATED { branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(relp3pri)

    CREATE (relp3pri)-[:IS_PROTECTED {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_false)
    CREATE (relp3pri)-[:IS_VISIBLE {branch: $main_branch, branch_level: 1, status: "active", from: $time_m120 }]->(bool_true)

    RETURN t1, t2, t3
    """
    await db.execute_query(query=query1, params=params)
    await db.execute_query(query=query_prefix + query2, params=params)
    await db.execute_query(query=query_prefix + query3, params=params)
    await db.execute_query(query=query_prefix + query4, params=params)
    return params


@pytest.fixture
async def base_dataset_04(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, register_organization_schema
) -> dict:
    time0 = pendulum.now(tz="UTC")
    params = {
        "main_branch": "main",
        "branch1": "branch1",
        "time0": time0.to_iso8601_string(),
        "time_m5": time0.subtract(seconds=5).to_iso8601_string(),
        "time_m10": time0.subtract(seconds=10).to_iso8601_string(),
        "time_m20": time0.subtract(seconds=20).to_iso8601_string(),
        "time_m30": time0.subtract(seconds=30).to_iso8601_string(),
        "time_m35": time0.subtract(seconds=35).to_iso8601_string(),
    }

    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Blue", description="The Blue tag")
    await blue.save(db=db, at=params["time_m30"])

    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="red", description="The red tag")
    await red.save(db=db, at=params["time_m30"])

    yellow = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await yellow.new(db=db, name="yellow", description="The yellow tag")
    await yellow.save(db=db, at=params["time_m30"])

    org1 = await Node.init(db=db, schema="CoreOrganization", branch=default_branch)
    await org1.new(db=db, name="org1", tags=[blue])
    await org1.save(db=db, at=params["time_m30"])

    branch1 = await create_branch(branch_name="branch1", db=db, at=params["time_m20"])

    org1_branch = await registry.manager.get_one(id=org1.id, branch=branch1, db=db)
    await org1_branch.tags.update(data=[blue, red], db=db)
    await org1_branch.save(db=db, at=params["time_m5"])

    org1_main = await registry.manager.get_one(id=org1.id, db=db)
    await org1_main.tags.update(data=[blue, yellow], db=db)
    await org1_main.save(db=db, at=params["time_m10"])

    params["blue"] = blue
    params["red"] = red
    params["yellow"] = yellow
    params["org1"] = org1

    return params


@pytest.fixture
async def choices_schema(db: InfrahubDatabase, default_branch: Branch, node_group_schema) -> None:
    SCHEMA: dict[str, Any] = {
        "generics": [
            {
                "name": "Choice",
                "namespace": "Base",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "color", "kind": "Text", "enum": ["red", "green", "blue"], "optional": True},
                    {"name": "measuring_system", "kind": "Text", "enum": ["metric"], "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                    {
                        "name": "section",
                        "kind": "Dropdown",
                        "optional": True,
                        "choices": [
                            {"name": "backend", "label": "Backend", "color": ""},
                            {"name": "frontend", "label": "Frontend", "color": "#0000ff"},
                        ],
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Choice",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "status", "kind": "Text", "enum": ["active", "passive"]},
                    {"name": "comment", "kind": "Text", "optional": True},
                    {
                        "name": "temperature_scale",
                        "kind": "Dropdown",
                        "optional": True,
                        "choices": [{"name": "celsius", "label": "Celsius"}],
                    },
                ],
                "inherit_from": ["BaseChoice"],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def car_person_schema_global(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema, data_schema
) -> None:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number", "branch": BranchSupportType.AGNOSTIC.value},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                    {"name": "is_electric", "kind": "Boolean"},
                ],
                "relationships": [
                    {"name": "owner", "peer": "TestPerson", "optional": False, "cardinality": "one"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many"}],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def car_person_data_generic(db: InfrahubDatabase, register_core_models_schema, car_person_schema_generics):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)
    c1 = await Node.init(db=db, schema="TestElectricCar")
    await c1.new(db=db, name="volt", nbr_seats=3, nbr_engine=4, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema="TestElectricCar")
    await c2.new(db=db, name="bolt", nbr_seats=2, nbr_engine=2, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema="TestGazCar")
    await c3.new(db=db, name="nolt", nbr_seats=4, mpg=25, owner=p2)
    await c3.save(db=db)
    c4 = await Node.init(db=db, schema="TestGazCar")
    await c4.new(db=db, name="focus", nbr_seats=5, mpg=30, owner=p2)
    await c4.save(db=db)

    query = """
    query {
        TestPerson {
            name {
                value
            }
            cars {
                name {
                    value
                }
            }
        }
    }
    """

    q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await q1.new(db=db, name="query01", query=query)
    await q1.save(db=db)

    r1 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await r1.new(db=db, name="repo01", location="git@github.com:user/repo01.git", commit="aaaaaaaaa")
    await r1.save(db=db)

    return {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "q1": q1,
        "r1": r1,
    }


@pytest.fixture
async def car_person_manufacturer_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                    {"name": "is_electric", "kind": "Boolean"},
                ],
                "relationships": [
                    {"name": "owner", "peer": "TestPerson", "optional": False, "cardinality": "one"},
                    {"name": "manufacturer", "peer": "TestManufacturer", "optional": False, "cardinality": "one"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many"}],
            },
            {
                "name": "Manufacturer",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many"}],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def car_person_schema_generics(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, data_schema
) -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "generics": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "order_by": ["name__value"],
                "include_in_menu": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "identifier": "person__car",
                        "optional": False,
                        "cardinality": "one",
                    },
                    {
                        "name": "previous_owner",
                        "peer": "TestPerson",
                        "identifier": "person_previous__car",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "Group",
                "namespace": "Core",
                "description": "Generic Group Object.",
                "label": "Group",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "members",
                        "peer": "CoreNode",
                        "optional": True,
                        "identifier": "group_member",
                        "cardinality": "many",
                    },
                    {
                        "name": "subscribers",
                        "peer": "CoreNode",
                        "optional": True,
                        "identifier": "group_subscriber",
                        "cardinality": "many",
                    },
                ],
            },
            {
                "name": "Node",
                "namespace": "Core",
                "description": "Base Node in Infrahub.",
                "label": "Node",
            },
        ],
        "nodes": [
            {
                "name": "StandardGroup",
                "namespace": "Core",
                "inherit_from": [InfrahubKind.GENERICGROUP],
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
            {
                "name": "ElectricCar",
                "namespace": "Test",
                "display_labels": ["name__value", "color__value"],
                "inherit_from": ["TestCar", "CoreArtifactTarget"],
                "default_filter": "name__value",
                "attributes": [
                    {"name": "nbr_engine", "kind": "Number"},
                ],
            },
            {
                "name": "GazCar",
                "namespace": "Test",
                "display_labels": ["name__value", "color__value"],
                "inherit_from": ["TestCar", "CoreArtifactTarget"],
                "default_filter": "name__value",
                "attributes": [
                    {"name": "mpg", "kind": "Number"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {"name": "cars", "peer": "TestCar", "identifier": "person__car", "cardinality": "many"}
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def car_person_generics_data(db: InfrahubDatabase, car_person_schema_generics) -> Dict[str, Node]:
    ecar = registry.schema.get(name="TestElectricCar")
    gcar = registry.schema.get(name="TestGazCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=ecar)
    await c1.new(db=db, name="volt", nbr_seats=4, nbr_engine=4, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=ecar)
    await c2.new(db=db, name="bolt", nbr_seats=4, nbr_engine=2, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=gcar)
    await c3.new(db=db, name="nolt", nbr_seats=4, mpg=25, owner=p2)
    await c3.save(db=db)

    nodes = {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
    }

    return nodes


@pytest.fixture
async def person_tag_schema(db: InfrahubDatabase, default_branch: Branch, data_schema) -> None:
    SCHEMA: Dict[str, Any] = {
        "nodes": [
            {
                "name": "Tag",
                "namespace": "Builtin",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "firstname__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "firstname", "kind": "Text"},
                    {"name": "lastname", "kind": "Text"},
                ],
                "relationships": [
                    {"name": "tags", "peer": InfrahubKind.TAG, "cardinality": "many", "direction": "inbound"},
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "identifier": "person_primary_tag",
                        "cardinality": "one",
                        "direction": "outbound",
                    },
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def person_john_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    return person


@pytest.fixture
async def person_jane_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Jane", height=180)
    await person.save(db=db)

    return person


@pytest.fixture
async def person_jim_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Jim", height=170)
    await person.save(db=db)

    return person


@pytest.fixture
async def person_albert_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Albert", height=160)
    await person.save(db=db)

    return person


@pytest.fixture
async def person_alfred_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alfred", height=160)
    await person.save(db=db)

    return person


@pytest.fixture
async def car_profile1_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", nbr_seats=5, is_electric=False)
    await profile.save(db=db)

    return profile


@pytest.fixture
async def car_accord_main(db: InfrahubDatabase, default_branch: Branch, person_john_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)

    return car


@pytest.fixture
async def car_volt_main(db: InfrahubDatabase, default_branch: Branch, person_john_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=person_john_main.id)
    await car.save(db=db)

    return car


@pytest.fixture
async def car_prius_main(db: InfrahubDatabase, default_branch: Branch, person_john_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="prius", nbr_seats=5, is_electric=True, owner=person_john_main.id)
    await car.save(db=db)

    return car


@pytest.fixture
async def car_camry_main(db: InfrahubDatabase, default_branch: Branch, person_jane_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="camry", nbr_seats=5, is_electric=False, owner=person_jane_main.id)
    await car.save(db=db)

    return car


@pytest.fixture
async def car_yaris_main(db: InfrahubDatabase, default_branch: Branch, person_jane_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="yaris", nbr_seats=4, is_electric=False, owner=person_jane_main.id)
    await car.save(db=db)

    return car


@pytest.fixture
async def tag_blue_main(db: InfrahubDatabase, default_branch: Branch, person_tag_schema) -> Node:
    tag = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await tag.new(db=db, name="Blue", description="The Blue tag")
    await tag.save(db=db)

    return tag


@pytest.fixture
async def tag_red_main(db: InfrahubDatabase, default_branch: Branch, person_tag_schema) -> Node:
    tag = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await tag.new(db=db, name="Red", description="The Red tag")
    await tag.save(db=db)

    return tag


@pytest.fixture
async def tag_black_main(db: InfrahubDatabase, default_branch: Branch, person_tag_schema) -> Node:
    tag = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await tag.new(db=db, name="Black", description="The Black tag")
    await tag.save(db=db)

    return tag


@pytest.fixture
async def person_jack_main(db: InfrahubDatabase, default_branch: Branch, person_tag_schema) -> Node:
    obj = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await obj.new(db=db, firstname="Jack", lastname="Russell")
    await obj.save(db=db)

    return obj


@pytest.fixture
async def person_jack_primary_tag_main(db: InfrahubDatabase, person_tag_schema, tag_blue_main: Node) -> Node:
    obj = await Node.init(db=db, schema="TestPerson")
    await obj.new(db=db, firstname="Jake", lastname="Russell", primary_tag=tag_blue_main)
    await obj.save(db=db)
    return obj


@pytest.fixture
async def person_jack_tags_main(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema, tag_blue_main: Node, tag_red_main: Node
) -> Node:
    obj = await Node.init(db=db, schema="TestPerson")
    await obj.new(db=db, firstname="Jake", lastname="Russell", tags=[tag_blue_main, tag_red_main])
    await obj.save(db=db)
    return obj


@pytest.fixture
async def group_group1_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema,
) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await obj.new(db=db, name="group1")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def group_group1_members_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema,
    person_john_main: Node,
    person_jim_main: Node,
) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await obj.new(db=db, name="group1", members=[person_john_main, person_jim_main])
    await obj.save(db=db)

    return obj


@pytest.fixture
async def group_group2_members_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema,
    person_john_main: Node,
    person_albert_main: Node,
) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await obj.new(db=db, name="group2", members=[person_john_main, person_albert_main])
    await obj.save(db=db)

    return obj


@pytest.fixture
async def group_group1_subscribers_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await obj.new(db=db, name="group1", subscribers=[person_john_main, person_jim_main, person_albert_main])
    await obj.save(db=db)

    return obj


@pytest.fixture
async def group_group2_subscribers_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema,
    person_john_main: Node,
    person_jim_main: Node,
    car_volt_main: Node,
    car_accord_main: Node,
) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=default_branch)
    await obj.new(db=db, name="group2", subscribers=[person_john_main, person_jim_main, car_volt_main, car_accord_main])
    await obj.save(db=db)

    return obj


@pytest.fixture
async def all_attribute_types_schema(
    db: InfrahubDatabase, default_branch: Branch, group_schema, data_schema
) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "AllAttributeTypes",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "optional": True},
            {"name": "mystring", "kind": "Text", "optional": True},
            {"name": "mybool", "kind": "Boolean", "optional": True},
            {"name": "myint", "kind": "Number", "optional": True},
            {"name": "mylist", "kind": "List", "optional": True},
            {"name": "myjson", "kind": "JSON", "optional": True},
            {"name": "ipaddress", "kind": "IPHost", "optional": True},
            {"name": "prefix", "kind": "IPNetwork", "optional": True},
        ],
    }

    node_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=node_schema.kind, schema=node_schema, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node_schema


@pytest.fixture
async def all_attribute_default_types_schema(
    db: InfrahubDatabase, default_branch: Branch, group_schema, data_schema
) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "AllAttributeTypes",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "optional": True},
            {"name": "mystring", "kind": "Text", "optional": True},
            {"name": "mybool", "kind": "Boolean", "optional": True},
            {"name": "myint", "kind": "Number", "optional": True},
            {"name": "mylist", "kind": "List", "optional": True},
            {"name": "myjson", "kind": "JSON", "optional": True},
            {"name": "mystring_default", "kind": "Text", "optional": True, "default_value": "a string"},
            {"name": "mybool_default", "kind": "Boolean", "optional": True, "default_value": False},
            {"name": "myint_default", "kind": "Number", "optional": True, "default_value": 10},
            {"name": "mylist_default", "kind": "List", "optional": True, "default_value": [10, 11, 12]},
            {"name": "myjson_default", "kind": "JSON", "optional": True, "default_value": {"name": "value"}},
            {"name": "mystring_none", "kind": "Text", "optional": True},
            {"name": "mybool_none", "kind": "Boolean", "optional": True},
            {"name": "myint_none", "kind": "Number", "optional": True},
            {"name": "mylist_none", "kind": "List", "optional": True},
            {"name": "myjson_none", "kind": "JSON", "optional": True},
        ],
    }

    node_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=node_schema.kind, schema=node_schema, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node_schema


@pytest.fixture
async def criticality_schema(db: InfrahubDatabase, default_branch: Branch, group_schema, data_schema) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "label", "kind": "Text", "optional": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "mylist", "kind": "List", "default_value": ["one", "two"]},
            {"name": "is_true", "kind": "Boolean", "default_value": True},
            {"name": "is_false", "kind": "Boolean", "default_value": False},
            {"name": "json_no_default", "kind": "JSON", "optional": True},
            {"name": "json_default", "kind": "JSON", "default_value": {"value": "bob"}},
            {"name": "description", "kind": "Text", "optional": True},
            {
                "name": "status",
                "kind": "Dropdown",
                "optional": True,
                "choices": [
                    {"name": "active", "color": "#00ff00", "description": "Online things"},
                    {"name": "passive", "label": "Redundancy nodes not in the active path"},
                ],
            },
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    return registry.schema.get(name=node.kind, branch=default_branch.name)


@pytest.fixture
async def criticality_low(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    obj = await Node.init(db=db, schema=criticality_schema)
    await obj.new(db=db, name="low", level=4)
    await obj.save(db=db)

    return obj


@pytest.fixture
async def criticality_medium(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    obj = await Node.init(db=db, schema=criticality_schema)
    await obj.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def criticality_high(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    obj = await Node.init(db=db, schema=criticality_schema)
    await obj.new(db=db, name="high", level=2, description="My other desc", color="#333333")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def generic_vehicule_schema(db: InfrahubDatabase, default_branch: Branch) -> GenericSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Vehicule",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
        ],
    }

    node = GenericSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node


@pytest.fixture
async def car_schema(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema, data_schema) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Car",
        "namespace": "Test",
        "inherit_from": ["TestVehicule"],
        "attributes": [
            {"name": "nbr_doors", "kind": "Number"},
        ],
    }

    node = NodeSchema(**SCHEMA)
    node.inherit_from_interface(interface=generic_vehicule_schema)
    registry.schema.set(name=node.kind, schema=node)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node


@pytest.fixture
async def motorcycle_schema(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Motorcycle",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
            {"name": "nbr_seats", "kind": "Number"},
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node


@pytest.fixture
async def truck_schema(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Truck",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
            {"name": "nbr_axles", "kind": "Number"},
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node


@pytest.fixture
async def boat_schema(
    db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema, person_schema
) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Boat",
        "namespace": "Test",
        "inherit_from": ["TestVehicule"],
        "attributes": [
            {"name": "has_sails", "kind": "Boolean"},
        ],
        "relationships": [
            {"name": "owners", "peer": "TestPerson", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    node.inherit_from_interface(interface=generic_vehicule_schema)
    registry.schema.set(name=node.kind, schema=node)
    registry.schema.process_schema_branch(name=default_branch.name)
    return node


@pytest.fixture
async def person_schema(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema) -> NodeSchema:
    SCHEMA: dict[str, Any] = {
        "name": "Person",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "vehicules", "peer": "TestVehicule", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node)
    registry.schema.process_schema_branch(name=default_branch.name)


@pytest.fixture
async def vehicule_person_schema(
    db: InfrahubDatabase, generic_vehicule_schema, car_schema, boat_schema, motorcycle_schema
) -> None:
    return None


@pytest.fixture
async def fruit_tag_schema(db: InfrahubDatabase, group_schema, data_schema) -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Tag",
                "namespace": "Builtin",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "color", "kind": "Text", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "Fruit",
                "namespace": "Garden",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [{"name": "tags", "peer": InfrahubKind.TAG, "cardinality": "many", "optional": False}],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema)
    return schema


@pytest.fixture
async def fruit_tag_schema_global(db: InfrahubDatabase, group_schema, data_schema) -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Tag",
                "namespace": "Builtin",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {
                        "name": "color",
                        "kind": "Text",
                        "default_value": "#444444",
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {"name": "related_tags", "peer": InfrahubKind.TAG, "cardinality": "many", "optional": True},
                    {"name": "related_fruits", "peer": "GardenFruit", "cardinality": "many", "optional": True},
                ],
            },
            {
                "name": "Fruit",
                "namespace": "Garden",
                "default_filter": "name__value",
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                    {
                        "name": "branch_aware_attr",
                        "kind": "Text",
                        "optional": True,
                        "branch": BranchSupportType.AWARE.value,
                    },
                ],
                "relationships": [
                    {"name": "tags", "peer": InfrahubKind.TAG, "cardinality": "many", "optional": True},
                    {"name": "related_fruits", "peer": "GardenFruit", "cardinality": "many", "optional": True},
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema)
    return schema


@pytest.fixture
async def hierarchical_location_schema_simple(db: InfrahubDatabase, default_branch: Branch) -> None:
    SCHEMA: dict[str, Any] = {
        "generics": [
            {
                "name": "Generic",
                "namespace": "Location",
                "default_filter": "name__value",
                "hierarchical": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "status", "kind": "Text", "enum": ["online", "offline"], "default_value": "online"},
                ],
                "relationships": [
                    {"name": "things", "peer": "TestThing", "cardinality": "many", "optional": True},
                ],
            }
        ],
        "nodes": [
            {
                "name": "Region",
                "namespace": "Location",
                "default_filter": "name__value",
                "inherit_from": ["LocationGeneric"],
                "parent": "",
                "children": "LocationSite",
            },
            {
                "name": "Site",
                "namespace": "Location",
                "default_filter": "name__value",
                "inherit_from": ["LocationGeneric"],
                "parent": "LocationRegion",
                "children": "LocationRack",
            },
            {
                "name": "Rack",
                "namespace": "Location",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "inherit_from": ["LocationGeneric"],
                "parent": "LocationSite",
                "children": "",
            },
            {
                "name": "Thing",
                "namespace": "Test",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "location", "peer": "LocationGeneric", "cardinality": "one", "optional": False},
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def hierarchical_location_schema(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema_simple, register_core_models_schema
) -> None: ...


@pytest.fixture
async def hierarchical_location_data_simple(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema_simple
) -> Dict[str, Node]:
    return await _build_hierarchical_location_data(db=db)


@pytest.fixture
async def hierarchical_location_data(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema
) -> Dict[str, Node]:
    return await _build_hierarchical_location_data(db=db)


async def _build_hierarchical_location_data(db: InfrahubDatabase) -> Dict[str, Node]:
    REGIONS = (
        ("north-america",),
        ("europe",),
        ("asia",),
    )

    SITES = (
        ("paris", "europe"),
        ("london", "europe"),
        ("chicago", "north-america"),
        ("seattle", "north-america"),
        ("beijing", "asia"),
        ("singapore", "asia"),
    )
    NBR_RACKS_PER_SITE = 2

    nodes = {}

    for region in REGIONS:
        obj = await Node.init(db=db, schema="LocationRegion")
        await obj.new(db=db, name=region[0])
        await obj.save(db=db)
        nodes[obj.name.value] = obj

    for site in SITES:
        obj = await Node.init(db=db, schema="LocationSite")
        await obj.new(db=db, name=site[0], parent=site[1])
        await obj.save(db=db)
        nodes[obj.name.value] = obj

        for idx in range(1, NBR_RACKS_PER_SITE + 1):
            rack_name = f"{site[0]}-r{idx}"
            statuses = ["online", "offline"]
            obj = await Node.init(db=db, schema="LocationRack")
            await obj.new(db=db, name=rack_name, parent=site[0], status=statuses[idx - 1])
            await obj.save(db=db)
            nodes[obj.name.value] = obj

    return nodes


@pytest.fixture
async def hierarchical_location_data_thing(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: Dict[str, Node]
) -> Dict[str, Node]:
    nodes = {}
    for item_name, item in hierarchical_location_data.items():
        obj = await Node.init(db=db, schema="TestThing")
        obj_name = f"thing-{item_name}"
        await obj.new(db=db, name=obj_name, location=item.id)
        await obj.save(db=db)
        nodes[obj_name] = obj

    nodes.update(hierarchical_location_data)
    return nodes


@pytest.fixture
async def hierarchical_groups_data(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema
) -> Dict[str, Node]:
    def batched(iterable, n):
        """
        Local implementation of the new batched function that was added to itertools in 3.12
        https://docs.python.org/3/library/itertools.html
        """
        # batched('ABCDEFG', 3) --> ABC DEF G
        if n < 1:
            raise ValueError("n must be at least one")
        it = iter(iterable)
        while batch := tuple(islice(it, n)):
            yield batch

    GROUPS_DATA = (
        ("grp1", None),
        ("grp11", "grp1"),
        ("grp12", "grp1"),
        ("grp111", "grp11"),
        ("grp112", "grp11"),
        ("grp121", "grp12"),
        ("grp122", "grp12"),
    )

    tags = []
    nbr_tags_per_group = 2
    for idx in range(len(GROUPS_DATA) * nbr_tags_per_group):
        obj = await Node.init(db=db, schema="BuiltinTag")
        await obj.new(db=db, name=f"tag-{idx}")
        await obj.save(db=db)
        tags.append(obj)

    batched_tags = list(batched(tags, nbr_tags_per_group))

    for idx, group in enumerate(GROUPS_DATA):
        grp = await Node.init(db=db, schema="CoreStandardGroup")
        await grp.new(db=db, name=group[0], parent=group[1], members=[tag.id for tag in batched_tags[idx]])
        await grp.save(db=db)

    return {tag.id: tag for tag in tags}


@pytest.fixture
async def prefix_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Prefix",
                "namespace": "Test",
                "attributes": [
                    {"name": "prefix", "kind": "IPNetwork", "unique": True},
                    {"name": "name", "kind": "Text"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "Ip",
                "namespace": "Test",
                "attributes": [
                    {"name": "address", "kind": "IPHost", "unique": True},
                    {"name": "name", "kind": "Text"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema)
    return schema


@pytest.fixture
async def reset_registry(db: InfrahubDatabase) -> None:
    registry.delete_all()


@pytest.fixture
async def delete_all_nodes_in_db(db: InfrahubDatabase) -> None:
    await delete_all_nodes(db=db)


@pytest.fixture
async def empty_database(db: InfrahubDatabase, delete_all_nodes_in_db) -> None:
    await create_root_node(db=db)


@pytest.fixture
async def init_db(empty_database, db: InfrahubDatabase) -> None:
    await first_time_initialization(db=db)
    await initialization(db=db)


@pytest.fixture
async def init_nodes_registry(db: InfrahubDatabase) -> None:
    registry.node["Node"] = Node
    registry.node["BuiltinIPPrefix"] = BuiltinIPPrefix
    registry.node["CorePrefixPool"] = CorePrefixPool
    registry.node["CorePrefixGlobalPool"] = CorePrefixGlobalPool


@pytest.fixture
async def organization_schema() -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Organization",
                "namespace": "Core",
                "description": "An organization represent a legal entity, a company.",
                "include_in_menu": True,
                "label": "Organization",
                "icon": "mdi:domain",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": InfrahubKind.TAG,
                        "kind": "Attribute",
                        "optional": True,
                        "cardinality": "many",
                    },
                ],
            },
        ]
    }

    return SchemaRoot(**SCHEMA)


@pytest.fixture
async def builtin_schema() -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Status",
                "namespace": "Builtin",
                "description": "Represent the status of an object: active, maintenance",
                "include_in_menu": True,
                "icon": "mdi:list-status",
                "label": "Status",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "Role",
                "namespace": "Builtin",
                "description": "Represent the role of an object",
                "include_in_menu": True,
                "icon": "mdi:ballot",
                "label": "Role",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
            {
                "name": "Site",
                "namespace": "Infra",
                "description": "A location represent a physical element site",
                "include_in_menu": True,
                "icon": "mdi:map-marker-radius-outline",
                "label": "Site",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                    {"name": "type", "kind": "Text"},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": InfrahubKind.TAG,
                        "kind": "Attribute",
                        "optional": True,
                        "cardinality": "many",
                    },
                ],
            },
            {
                "name": "Criticality",
                "namespace": "Builtin",
                "description": "Level of criticality expressed from 1 to 10.",
                "include_in_menu": True,
                "icon": "mdi:alert-octagon-outline",
                "label": "Criticality",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "level", "kind": "Number", "enum": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
        ]
    }

    return SchemaRoot(**SCHEMA)


@pytest.fixture
async def ipam_schema() -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "IPPrefix",
                "namespace": "Ipam",
                "default_filter": "prefix__value",
                "order_by": ["prefix__value"],
                "display_labels": ["prefix__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPPREFIX],
            },
            {
                "name": "IPAddress",
                "namespace": "Ipam",
                "default_filter": "address__value",
                "order_by": ["address__value"],
                "display_labels": ["address__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPADDRESS],
            },
        ],
    }

    return SchemaRoot(**SCHEMA)


@pytest.fixture
async def register_builtin_models_schema(default_branch: Branch, builtin_schema: SchemaRoot) -> SchemaBranch:
    schema_branch = registry.schema.register_schema(schema=builtin_schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture
async def register_organization_schema(default_branch: Branch, organization_schema: SchemaRoot) -> SchemaBranch:
    schema_branch = registry.schema.register_schema(schema=organization_schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture
async def register_core_schema_db(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema) -> None:
    await registry.schema.load_schema_to_db(schema=register_core_models_schema, branch=default_branch, db=db)
    updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema)


@pytest.fixture
async def register_account_schema(db: InfrahubDatabase) -> None:
    SCHEMAS_TO_REGISTER = [
        InfrahubKind.ACCOUNT,
        InfrahubKind.ACCOUNTTOKEN,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.REFRESHTOKEN,
    ]
    nodes = [item for item in core_models["nodes"] if f'{item["namespace"]}{item["name"]}' in SCHEMAS_TO_REGISTER]
    generics = [item for item in core_models["generics"] if f'{item["namespace"]}{item["name"]}' in SCHEMAS_TO_REGISTER]
    registry.schema.register_schema(schema=SchemaRoot(nodes=nodes, generics=generics))


@pytest.fixture
async def register_ipam_schema(default_branch: Branch, ipam_schema: SchemaRoot) -> SchemaBranch:
    schema_branch = registry.schema.register_schema(schema=ipam_schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture
async def register_ipam_extended_schema(default_branch: Branch, register_ipam_schema) -> SchemaBranch:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "MandatoryPrefix",
                "namespace": "Test",
                "description": "A model with a mandatory relationship to a BuiltinIPPrefix",
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "prefix",
                        "peer": "IpamIPPrefix",
                        "kind": "Attribute",
                        "optional": False,
                        "cardinality": "one",
                    },
                ],
            },
        ],
    }

    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**SCHEMA), branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture
async def create_test_admin(db: InfrahubDatabase, register_core_models_schema, data_schema) -> Node:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(
        db=db,
        name="test-admin",
        type="User",
        password=config.SETTINGS.security.initial_admin_password,
        role="admin",
    )
    await account.save(db=db)
    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(
        db=db,
        token="admin-security",
        account=account,
    )
    await token.save(db=db)

    return account


@pytest.fixture
async def session_admin(db: InfrahubDatabase, create_test_admin) -> AccountSession:
    session = AccountSession(authenticated=True, auth_type=AuthType.API, account_id=create_test_admin.id, role="admin")
    return session


@pytest.fixture
async def authentication_base(
    db: InfrahubDatabase,
    default_branch: Branch,
    create_test_admin,
    register_core_models_schema,
    register_builtin_models_schema,
    register_organization_schema,
):
    pass


@pytest.fixture
async def first_account(db: InfrahubDatabase, data_schema, node_group_schema, register_account_schema) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await obj.new(db=db, name="First Account", type="Git", password="FirstPassword123", role="read-write")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def second_account(db: InfrahubDatabase, data_schema, node_group_schema, register_account_schema) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await obj.new(db=db, name="Second Account", type="Git", password="SecondPassword123")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def repos_in_main(db: InfrahubDatabase, register_core_models_schema):
    repo01 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repo01.new(
        db=db,
        name="repo01",
        description="Repo 01 initial value",
        location="git@github.com:user/repo01.git",
        commit="aaaaaaaaaaa",
    )
    await repo01.save(db=db)

    repo02 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repo02.new(
        db=db,
        name="repo02",
        description="Repo 02 initial value",
        location="git@github.com:user/repo02.git",
        commit="bbbbbbbbbbb",
    )
    await repo02.save(db=db)

    return {"repo01": repo01, "repo02": repo02}


@pytest.fixture
async def read_only_repos_in_main(db: InfrahubDatabase, register_core_models_schema):
    repo01 = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
    await repo01.new(
        db=db,
        name="repo01",
        description="Repo 01 initial value",
        location="git@github.com:user/repo01.git",
        commit="aaaaaaaaaaa",
        ref="branch-1",
    )
    await repo01.save(db=db)

    repo02 = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
    await repo02.new(
        db=db,
        name="repo02",
        description="Repo 02 initial value",
        location="git@github.com:user/repo02.git",
        commit="bbbbbbbbbbb",
        ref="v1.2.3",
    )
    await repo02.save(db=db)

    return {"repo01": repo01, "repo02": repo02}


@pytest.fixture
async def mock_core_schema_01(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = helper.schema_file(file_name="core_schema_01.json")
    httpx_mock.add_response(method="GET", url="http://mock/api/schema/?branch=main", json=response_text)
    return httpx_mock


@pytest.fixture
def dataset01(init_db) -> None:
    ds01.load_data()


@pytest.fixture
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    # -----------------------
    # Namespace NS1
    # -----------------------

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net161 = await Node.init(db=db, schema=prefix_schema)
    await net161.new(db=db, prefix="2001:db8::/48", ip_namespace=ns1)
    await net161.save(db=db)

    net162 = await Node.init(db=db, schema=prefix_schema)
    await net162.new(db=db, prefix="2001:db8::/64", ip_namespace=ns1, parent=net161)
    await net162.save(db=db)

    net146 = await Node.init(db=db, schema=prefix_schema)
    await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net146.save(db=db)

    net140 = await Node.init(db=db, schema=prefix_schema)
    await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
    await net140.save(db=db)

    net142 = await Node.init(db=db, schema=prefix_schema)
    await net142.new(db=db, prefix="10.10.1.0/24", parent=net140, ip_namespace=ns1)
    await net142.save(db=db)

    net143 = await Node.init(db=db, schema=prefix_schema)
    await net143.new(db=db, prefix="10.10.1.0/27", parent=net142, ip_namespace=ns1)
    await net143.save(db=db)

    net144 = await Node.init(db=db, schema=prefix_schema)
    await net144.new(db=db, prefix="10.10.2.0/24", parent=net140, ip_namespace=ns1)
    await net144.save(db=db)

    net145 = await Node.init(db=db, schema=prefix_schema)
    await net145.new(db=db, prefix="10.10.3.0/27", parent=net140, ip_namespace=ns1)
    await net145.save(db=db)

    address10 = await Node.init(db=db, schema=address_schema)
    await address10.new(db=db, address="10.10.0.0", ip_prefix=net140, ip_namespace=ns1)
    await address10.save(db=db)

    address11 = await Node.init(db=db, schema=address_schema)
    await address11.new(db=db, address="10.10.1.1", ip_prefix=net143, ip_namespace=ns1)
    await address11.save(db=db)

    # -----------------------
    # Namespace NS2
    # -----------------------
    ns2 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns2.new(db=db, name="ns2")
    await ns2.save(db=db)

    net240 = await Node.init(db=db, schema=prefix_schema)
    await net240.new(db=db, prefix="10.10.0.0/15", ip_namespace=ns2)
    await net240.save(db=db)

    net241 = await Node.init(db=db, schema=prefix_schema)
    await net241.new(db=db, prefix="10.10.0.0/24", parent=net240, ip_namespace=ns2)
    await net241.save(db=db)

    net242 = await Node.init(db=db, schema=prefix_schema)
    await net242.new(db=db, prefix="10.10.4.0/27", parent=net240, ip_namespace=ns2)
    await net242.save(db=db)

    data = {
        "ns1": ns1,
        "ns2": ns2,
        "net161": net161,
        "net162": net162,
        "net140": net140,
        "net142": net142,
        "net143": net143,
        "net144": net144,
        "net145": net145,
        "net146": net146,
        "address10": address10,
        "address11": address11,
        "net240": net240,
        "net241": net241,
        "net242": net242,
    }
    return data


@pytest.fixture
async def ip_dataset_prefix_v4(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net146 = await Node.init(db=db, schema=prefix_schema)
    await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net146.save(db=db)

    net140 = await Node.init(db=db, schema=prefix_schema)
    await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
    await net140.save(db=db)

    net141 = await Node.init(db=db, schema=prefix_schema)
    await net141.new(db=db, prefix="10.11.0.0/16", ip_namespace=ns1, parent=net146)
    await net141.save(db=db)

    net142 = await Node.init(db=db, schema=prefix_schema)
    await net142.new(db=db, prefix="10.10.1.0/24", parent=net140, ip_namespace=ns1)
    await net142.save(db=db)

    net143 = await Node.init(db=db, schema=prefix_schema)
    await net143.new(db=db, prefix="10.10.1.0/27", parent=net142, ip_namespace=ns1)
    await net143.save(db=db)

    net144 = await Node.init(db=db, schema=prefix_schema)
    await net144.new(db=db, prefix="10.10.2.0/24", parent=net140, ip_namespace=ns1)
    await net144.save(db=db)

    net145 = await Node.init(db=db, schema=prefix_schema)
    await net145.new(db=db, prefix="10.10.3.0/27", parent=net140, ip_namespace=ns1)
    await net145.save(db=db)

    data = {
        "ns1": ns1,
        "net140": net140,
        "net141": net141,
        "net142": net142,
        "net143": net143,
        "net144": net144,
        "net145": net145,
        "net146": net146,
    }
    return data
