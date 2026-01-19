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

    # Query for any edges on the global branch with branch_level != 1
    query = "MATCH ()-[e {branch: $global_branch_name}]->() WHERE e.branch_level <> 1 RETURN count(*) AS num_edges"
    params = {"global_branch_name": GLOBAL_BRANCH_NAME}

    records = await db.execute_query(query=query, params=params, name="validate_global_branch_level")

    # Raise an error if any edges have incorrect branch_level
    if records:
        pytest.fail(f"Found {records[0]['num_edges']} edges on the global branch with branch_level != 1")
