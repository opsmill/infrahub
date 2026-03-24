"""Tests for validating branch-agnostic edge properties.

This module tests that edges on the global branch ("-global-") have the correct
branch_level property (should be 1 for all global branch edges).
"""

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase


async def assert_no_global_edges_with_wrong_branch_level(db: InfrahubDatabase) -> None:
    """Assert that all edges on the global branch have branch_level = 1.

    Fails the test if any edges on the global branch have branch_level != 1.
    """
    query = """
        MATCH ()-[e {branch: $global_branch_name}]->()
        WHERE e.branch_level <> 1
        RETURN count(*) AS num_edges
    """
    params = {"global_branch_name": GLOBAL_BRANCH_NAME}
    records = await db.execute_query(query=query, params=params, name="validate_global_branch_level")

    num_edges = records[0]["num_edges"] if records else 0
    if num_edges > 0:
        pytest.fail(f"Found {num_edges} edges on the global branch with branch_level != 1")


async def assert_no_global_edges_with_branch_level_zero(db: InfrahubDatabase) -> None:
    """Assert that no edges on the global branch have branch_level = 0.

    Fails the test if any edges on the global branch have branch_level = 0.
    This is a more specific check that catches the bug where branch-local fields
    incorrectly create edges on the global branch with branch_level = 0.
    """
    query = """
        MATCH ()-[e {branch: $global_branch_name}]->()
        WHERE e.branch_level = 0
        RETURN count(*) AS num_edges
    """
    params = {"global_branch_name": GLOBAL_BRANCH_NAME}
    records = await db.execute_query(query=query, params=params, name="validate_no_branch_level_zero")

    num_edges = records[0]["num_edges"] if records else 0
    if num_edges > 0:
        pytest.fail(f"Found {num_edges} edges on the global branch with branch_level = 0")


async def test_global_branch_edges_have_branch_level_1(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_branch_agnostic_schema: dict,
) -> None:
    """Test that all edges on the global branch have branch_level = 1.

    This test:
    1. Creates nodes using the car_person_branch_agnostic_schema (TestCar is AGNOSTIC)
    2. Creates objects on both the default branch and a user branch
    3. Validates that all edges on the "-global-" branch have branch_level = 1

    The test should fail if any edge on the global branch has a branch_level != 1,
    which would indicate a bug in how branch-agnostic edges are created.
    """
    # Register the schema
    schema_root = SchemaRoot(**car_person_branch_agnostic_schema)
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    # Create a person (AWARE node) on the default branch
    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, name="Person1")
    await person1.save(db=db)

    # Create a car (AGNOSTIC node) with agnostic_owner relationship on the default branch
    car1 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car1.new(db=db, name="Car1", agnostic_owner=person1)
    await car1.save(db=db)

    # Create a user branch
    user_branch = await create_branch(db=db, branch_name="test-branch")

    # Create another person on the user branch
    person2 = await Node.init(db=db, schema="TestPerson", branch=user_branch)
    await person2.new(db=db, name="Person2")
    await person2.save(db=db)

    # Create another car with agnostic_owner relationship on the user branch
    car2 = await Node.init(db=db, schema="TestCar", branch=user_branch)
    await car2.new(db=db, name="Car2", agnostic_owner=person2)
    await car2.save(db=db)

    await assert_no_global_edges_with_wrong_branch_level(db)


async def test_branch_local_edges_not_on_global_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
) -> None:
    """Test that branch-local attributes/relationships don't create edges on the global branch with branch_level=0.

    This test:
    1. Creates a schema with:
       - A branch-local node (TestLocalNode)
       - A branch-aware node with branch-local attribute and relationship (TestAwareNode)
       - A branch-global (agnostic) node with branch-local attribute and relationship (TestGlobalNode)
    2. Creates objects on both the default branch and a user branch
    3. Validates that:
       - All edges on the "-global-" branch have branch_level = 1
       - No edges on the "-global-" branch have branch_level = 0
    """
    # Define a schema with local, aware, and agnostic nodes
    schema_dict: dict = {
        "version": "1.0",
        "nodes": [
            # Branch-local node - all operations are branch-local
            {
                "name": "LocalNode",
                "namespace": "Test",
                "branch": "local",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "local_rel",
                        "peer": "TestAwareNode",
                        "optional": True,
                        "cardinality": "one",
                        "branch": "local",
                    },
                ],
            },
            # Branch-aware node with branch-local attribute and relationship
            {
                "name": "AwareNode",
                "namespace": "Test",
                "branch": "aware",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "local_attr", "kind": "Text", "optional": True, "branch": "local"},
                ],
                "relationships": [
                    {
                        "name": "local_rel",
                        "peer": "TestLocalNode",
                        "optional": True,
                        "cardinality": "one",
                        "branch": "local",
                    },
                ],
            },
            # Branch-global (agnostic) node with branch-local attribute and relationship
            {
                "name": "GlobalNode",
                "namespace": "Test",
                "branch": "agnostic",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "local_attr", "kind": "Text", "optional": True, "branch": "local"},
                ],
                "relationships": [
                    {
                        "name": "local_rel",
                        "peer": "TestLocalNode",
                        "optional": True,
                        "cardinality": "one",
                        "branch": "local",
                    },
                ],
            },
        ],
    }

    # Register the schema
    schema_root = SchemaRoot(**schema_dict)
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    # --- Create peer nodes on the default branch (these are just targets for relationships) ---

    # Create peer nodes without branch-local fields set
    aware_peer1 = await Node.init(db=db, schema="TestAwareNode", branch=default_branch)
    await aware_peer1.new(db=db, name="AwarePeer1")
    await aware_peer1.save(db=db)

    local_peer1 = await Node.init(db=db, schema="TestLocalNode", branch=default_branch)
    await local_peer1.new(db=db, name="LocalPeer1")
    await local_peer1.save(db=db)

    # --- Create test nodes on the default branch with all branch-local fields set at creation ---

    # Create LocalNode with local_rel set (tests branch-local node with branch-local relationship)
    local_node1 = await Node.init(db=db, schema="TestLocalNode", branch=default_branch)
    await local_node1.new(db=db, name="LocalNode1", local_rel=aware_peer1)
    await local_node1.save(db=db)

    # Create AwareNode with local_attr and local_rel set (tests branch-aware node with branch-local fields)
    aware_node1 = await Node.init(db=db, schema="TestAwareNode", branch=default_branch)
    await aware_node1.new(db=db, name="AwareNode1", local_attr="local_value_1", local_rel=local_peer1)
    await aware_node1.save(db=db)

    # Create GlobalNode with local_attr and local_rel set (tests branch-agnostic node with branch-local fields)
    global_node1 = await Node.init(db=db, schema="TestGlobalNode", branch=default_branch)
    await global_node1.new(db=db, name="GlobalNode1", local_attr="global_local_value_1", local_rel=local_peer1)
    await global_node1.save(db=db)

    # --- Create a user branch and nodes on it ---

    user_branch = await create_branch(db=db, branch_name="test-branch-local")

    # --- Create peer nodes on the user branch ---

    aware_peer2 = await Node.init(db=db, schema="TestAwareNode", branch=user_branch)
    await aware_peer2.new(db=db, name="AwarePeer2")
    await aware_peer2.save(db=db)

    local_peer2 = await Node.init(db=db, schema="TestLocalNode", branch=user_branch)
    await local_peer2.new(db=db, name="LocalPeer2")
    await local_peer2.save(db=db)

    # --- Create test nodes on the user branch with all branch-local fields set at creation ---

    # Create LocalNode with local_rel set
    local_node2 = await Node.init(db=db, schema="TestLocalNode", branch=user_branch)
    await local_node2.new(db=db, name="LocalNode2", local_rel=aware_peer2)
    await local_node2.save(db=db)

    # Create AwareNode with local_attr and local_rel set
    aware_node2 = await Node.init(db=db, schema="TestAwareNode", branch=user_branch)
    await aware_node2.new(db=db, name="AwareNode2", local_attr="local_value_2", local_rel=local_peer2)
    await aware_node2.save(db=db)

    # Create GlobalNode with local_attr and local_rel set
    global_node2 = await Node.init(db=db, schema="TestGlobalNode", branch=user_branch)
    await global_node2.new(db=db, name="GlobalNode2", local_attr="global_local_value_2", local_rel=local_peer2)
    await global_node2.save(db=db)

    # --- Validate that all edges on the global branch have correct branch_level ---
    await assert_no_global_edges_with_wrong_branch_level(db)
    await assert_no_global_edges_with_branch_level_zero(db)
