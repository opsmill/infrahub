import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m075_finish_deleting_branches import Migration075
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchNotFoundError, NodeNotFoundError


async def _branch_edge_count(db: InfrahubDatabase, branch_name: str) -> int:
    results = await db.execute_query(
        query="MATCH ()-[e]->() WHERE e.branch = $branch_name RETURN count(e) AS count",
        params={"branch_name": branch_name},
    )
    return results[0]["count"]


async def _add_tag(db: InfrahubDatabase, branch: Branch, name: str) -> Node:
    node = await Node.init(db=db, branch=branch, schema="BuiltinTag")
    await node.new(db=db, name=name)
    await node.save(db=db)
    return node


async def test_migration_075(db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None) -> None:
    """A branch abandoned in DELETING loses every edge, while the other branches keep all of theirs."""
    healthy_branch = await create_branch(db=db, branch_name="healthy-branch")
    stalled_branch = await create_branch(db=db, branch_name="stalled-branch")

    node_on_main = await _add_tag(db=db, branch=default_branch, name="node-on-main")
    node_on_healthy = await _add_tag(db=db, branch=healthy_branch, name="node-on-healthy-branch")
    node_on_stalled = await _add_tag(db=db, branch=stalled_branch, name="node-on-stalled-branch")

    # Reproduce what a failed delete leaves behind: the status set, the data still present.
    stalled_branch.status = BranchStatus.DELETING
    await stalled_branch.save(db=db)

    edges_before = {
        name: await _branch_edge_count(db=db, branch_name=name)
        for name in (default_branch.name, healthy_branch.name, stalled_branch.name)
    }
    # Every branch has to start with edges, otherwise the assertions below prove nothing.
    assert all(count > 0 for count in edges_before.values()), edges_before

    migration = Migration075()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    edges_after = {
        name: await _branch_edge_count(db=db, branch_name=name)
        for name in (default_branch.name, healthy_branch.name, stalled_branch.name)
    }

    # The abandoned branch is emptied; the untouched branches keep exactly what they had.
    assert edges_after == {
        default_branch.name: edges_before[default_branch.name],
        healthy_branch.name: edges_before[healthy_branch.name],
        stalled_branch.name: 0,
    }

    # The branch node is gone too, along with the data that hung off it.
    with pytest.raises(BranchNotFoundError):
        await Branch.get_by_name(db=db, name=stalled_branch.name, ignore_deleting=False)
    with pytest.raises(NodeNotFoundError):
        await NodeManager.get_one(db=db, branch=default_branch, id=node_on_stalled.id, raise_on_error=True)

    # The surviving branches are still usable, not merely still edged.
    reloaded_healthy = await Branch.get_by_name(db=db, name=healthy_branch.name)
    assert reloaded_healthy.status == BranchStatus.OPEN
    retrieved_on_healthy = await NodeManager.get_one(db=db, branch=healthy_branch, id=node_on_healthy.id)
    assert retrieved_on_healthy is not None
    assert retrieved_on_healthy.get_attribute("name").value == "node-on-healthy-branch"
    retrieved_on_main = await NodeManager.get_one(db=db, branch=default_branch, id=node_on_main.id)
    assert retrieved_on_main is not None
    assert retrieved_on_main.get_attribute("name").value == "node-on-main"


async def test_migration_075_no_deleting_branches(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None
) -> None:
    """With nothing to finish, every branch keeps every edge."""
    branch = await create_branch(db=db, branch_name="untouched-branch")
    await _add_tag(db=db, branch=default_branch, name="node-on-main")
    await _add_tag(db=db, branch=branch, name="node-on-untouched-branch")

    edges_before = {
        name: await _branch_edge_count(db=db, branch_name=name) for name in (default_branch.name, branch.name)
    }
    assert all(count > 0 for count in edges_before.values()), edges_before

    migration = Migration075()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    edges_after = {
        name: await _branch_edge_count(db=db, branch_name=name) for name in (default_branch.name, branch.name)
    }
    assert edges_after == edges_before

    reloaded = await Branch.get_by_name(db=db, name=branch.name)
    assert reloaded.status == BranchStatus.OPEN
