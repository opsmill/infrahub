import pytest

from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m032_cleanup_orphaned_branch_relationships import Migration032
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError


async def test_migration_032(db: InfrahubDatabase, default_branch: Branch, person_tag_schema) -> None:
    # Step 1: Create a couple of branches
    branch1 = await create_branch(db=db, branch_name="test-branch-1")
    branch2 = await create_branch(db=db, branch_name="test-branch-2")
    branch3 = await create_branch(db=db, branch_name="test-branch-3")

    # Step 2: Add a Node on each branch
    node0 = await Node.init(db=db, branch=default_branch, schema="BuiltinTag")
    await node0.new(db=db, name="node-on-main")
    await node0.save(db=db)

    node1 = await Node.init(db=db, branch=branch1, schema="BuiltinTag")
    await node1.new(db=db, name="node-on-branch-1")
    await node1.save(db=db)

    node2 = await Node.init(db=db, branch=branch2, schema="BuiltinTag")
    await node2.new(db=db, name="node-on-branch-2")
    await node2.save(db=db)

    node3 = await Node.init(db=db, branch=branch3, schema="BuiltinTag")
    await node3.new(db=db, name="node-on-branch-3")
    await node3.save(db=db)

    # Step 3: Make Node on branch3 partially deleted
    query = """
MATCH ()-[e]->()
WHERE e.branch = "test-branch-3"
SET e.branch = "dead-branch"
    """
    await db.execute_query(query=query)

    # Step 4: Run Migration032
    migration = Migration032()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    # Step 5: Check that the nodes created in step 2 can be retrieved successfully
    retrieved_node0 = await NodeManager.get_one(db=db, branch=default_branch, id=node0.id)
    assert retrieved_node0 is not None
    assert retrieved_node0.name.value == "node-on-main"
    retrieved_node1 = await NodeManager.get_one(db=db, branch=branch1, id=node1.id)
    assert retrieved_node1 is not None
    assert retrieved_node1.name.value == "node-on-branch-1"
    retrieved_node2 = await NodeManager.get_one(db=db, branch=branch2, id=node2.id)
    assert retrieved_node2 is not None
    assert retrieved_node2.name.value == "node-on-branch-2"

    # Step 6: Validate node3 cannot be retrieved
    with pytest.raises(NodeNotFoundError):
        await NodeManager.get_one(db=db, branch=branch3, id=node3.id, raise_on_error=True)

    # Step 7: make sure only the valid branches are still in the database
    query = """MATCH ()-[e]->() WHERE e.branch IS NOT NULL RETURN DISTINCT e.branch AS branch_name"""
    results = await db.execute_query(query=query)
    branch_names = {r["branch_name"] for r in results}
    assert branch_names == {branch1.name, branch2.name, default_branch.name}
