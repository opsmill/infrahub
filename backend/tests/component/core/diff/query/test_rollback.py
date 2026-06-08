from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.rollback import RollbackQuery
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def _count_branch_edges_at(db: InfrahubDatabase, branch: Branch, at: Timestamp) -> int:
    result = await db.execute_query(
        query="MATCH ()-[r {from: $at, branch: $branch}]->() RETURN count(r) AS c",
        params={"at": at.to_string(), "branch": branch.name},
    )
    return result[0].get("c")


async def test_rollback_query_with_empty_node_uuids(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    """RollbackQuery called with the default empty node_uuids list clears every edge created.

    at the given timestamp on the branch and orphan-deletes the affected vertices, while
    leaving nodes and edges from other timestamps untouched.

    """
    at_kept = Timestamp()
    kept = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await kept.new(db=db, name="Bob", height=180)
    await kept.save(db=db, at=at_kept)

    at_rolled_back = Timestamp()
    discarded = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await discarded.new(db=db, name="Carol", height=165)
    await discarded.save(db=db, at=at_rolled_back)

    edges_before = await _count_branch_edges_at(db=db, branch=default_branch, at=at_rolled_back)
    assert edges_before > 0, "Saving a node should create at least one edge stamped with `at`"

    rollback_query = await RollbackQuery.init(db=db, target_branch=default_branch, at=at_rolled_back)
    await rollback_query.execute(db=db)

    loaded_kept = await NodeManager.get_one(db=db, id=kept.id, branch=default_branch)
    assert loaded_kept is not None, "Node created at a different timestamp must survive rollback"
    assert loaded_kept.get_attribute("name").value == "Bob"

    loaded_discarded = await NodeManager.get_one(db=db, id=discarded.id, branch=default_branch)
    assert loaded_discarded is None, "Node created at the rollback timestamp must be removed"

    edges_after = await _count_branch_edges_at(db=db, branch=default_branch, at=at_rolled_back)
    assert edges_after == 0, "Rollback should delete every edge stamped with `at` on the branch"
