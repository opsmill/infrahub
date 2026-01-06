from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m030_illegal_edges import Migration030
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_edges_added_after_node_delete


async def _add_attribute(db: InfrahubDatabase, node_id: str, branch: Branch, at: Timestamp) -> None:
    query = """
MATCH (n:Node {uuid: $node_id})
CREATE (attr:Attribute {name: "smell"})
CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch_name, branch_level: $branch_level, status: "active", from: $at}]->(attr)
MERGE (attr_val:AttributeValue {value: "good"})
MERGE (bool_true:Boolean {value: true})
WITH attr, attr_val, bool_true LIMIT 1
CREATE (attr)-[:HAS_VALUE {branch: $branch_name, branch_level: $branch_level, status: "active", from: $at}]->(attr_val)
    """
    await db.execute_query(
        query=query,
        params={
            "node_id": node_id,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": at.to_string(),
        },
    )


async def _get_active_attributes(db: InfrahubDatabase) -> dict[str, set[str]]:
    """Return a dict of {node_id: {branch_name, ...}} for nodes that still have the testing attribute"""
    query = """
MATCH (n:Node)-[has_attr:HAS_ATTRIBUTE]->(:Attribute {name: "smell"})-[:HAS_VALUE]->()
WITH DISTINCT n.uuid AS node_id, has_attr.branch AS branch
RETURN node_id, collect(branch) AS branches
    """
    results = await db.execute_query(query=query)
    response: dict[str, set[str]] = {}
    for result in results:
        node_id = result.get("node_id")
        branches = set(result.get("branches"))
        response[node_id] = branches
    return response


async def test_migration_030(
    db: InfrahubDatabase,
    person_tag_schema,
    default_branch,
) -> None:
    create_before_branch = await Node.init(db=db, schema="BuiltinTag")
    await create_before_branch.new(db=db, name="create-before-branch")
    await create_before_branch.save(db=db)

    delete_before_branch = await Node.init(db=db, schema="BuiltinTag")
    await delete_before_branch.new(db=db, name="delete-before-branch")
    await delete_before_branch.save(db=db)
    await delete_before_branch.delete(db=db)

    delete_after_branch = await Node.init(db=db, schema="BuiltinTag")
    await delete_after_branch.new(db=db, name="delete-after-branch")
    await delete_after_branch.save(db=db)

    branch = await create_branch(db=db, branch_name="branch-migration030")

    await delete_after_branch.delete(db=db)
    delete_on_branch = await NodeManager.get_one(db=db, branch=branch, id=create_before_branch.id)
    await delete_on_branch.delete(db=db)

    create_on_branch = await Node.init(db=db, branch=branch, schema="BuiltinTag")
    await create_on_branch.new(db=db, name="create-on-branch")
    await create_on_branch.save(db=db)

    intra_branch_delete = await Node.init(db=db, branch=branch, schema="BuiltinTag")
    await intra_branch_delete.new(db=db, name="delete-on-branch")
    await intra_branch_delete.save(db=db)
    await intra_branch_delete.delete(db=db)

    right_now = Timestamp()
    all_nodes = [
        create_before_branch,
        delete_before_branch,
        delete_after_branch,
        create_on_branch,
        intra_branch_delete,
    ]
    for node in all_nodes:
        # add Attribute to all nodes on main
        await _add_attribute(db=db, node_id=node.id, branch=default_branch, at=right_now)
        # add Attribute to all nodes on branch
        await _add_attribute(db=db, node_id=node.id, branch=branch, at=right_now)

    migration = Migration030()
    execution_result = await migration.execute(db=db, at=Timestamp())
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    nodes_with_attribute_map = await _get_active_attributes(db=db)
    assert nodes_with_attribute_map == {
        # deleted on branch
        create_before_branch.id: {default_branch.name},
        # should not have either branch, so excluded
        # delete_before_branch.id: {},
        delete_after_branch.id: {branch.name},
        create_on_branch.id: {default_branch.name, branch.name},
        intra_branch_delete.id: {default_branch.name},
    }

    await verify_no_edges_added_after_node_delete(db=db)
