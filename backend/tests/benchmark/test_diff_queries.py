"""Benchmarks of the diff queries that select edges by the time they were opened or closed."""

from collections.abc import Callable
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import BuiltinTag
from infrahub.core.query.diff import DiffCountChanges, DiffFieldNodesQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

TAGS_ON_DEFAULT_BRANCH = 20
TAGS_CHANGED_ON_BRANCH = 10


@pytest.fixture
async def branch_with_changes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> Branch:
    """A branch that updates an attribute and adds a relationship on nodes of the default branch."""
    tags = []
    for index in range(TAGS_ON_DEFAULT_BRANCH):
        tag = await Node.init(db=db, schema="BuiltinTag", branch=default_branch)
        await tag.new(db=db, name=f"tag-{index}")
        await tag.save(db=db)
        tags.append(tag)

    branch = await create_branch(db=db, branch_name="branch")
    changed_tags = tags[:TAGS_CHANGED_ON_BRANCH]
    group = await Node.init(db=db, schema="CoreStandardGroup", branch=branch)
    await group.new(db=db, name="group", members=changed_tags)
    await group.save(db=db)
    for tag in changed_tags:
        branch_tag = await NodeManager.get_one(db=db, id=tag.id, branch=branch, kind=BuiltinTag, raise_on_error=True)
        branch_tag.description.value = "changed on the branch"
        await branch_tag.save(db=db)

    return branch


async def count_changes(
    db: InfrahubDatabase, branch_names: list[str], diff_from: Timestamp, diff_to: Timestamp
) -> dict[str, int]:
    query = await DiffCountChanges.init(db=db, branch_names=branch_names, diff_from=diff_from, diff_to=diff_to)
    await query.execute(db=db)
    return query.get_num_changes_by_branch()


async def list_field_nodes(
    db: InfrahubDatabase, base_branch: Branch, branch: Branch, diff_from: Timestamp, diff_to: Timestamp
) -> list[str]:
    query = await DiffFieldNodesQuery.init(
        db=db,
        branch=branch,
        base_branch=base_branch,
        diff_branch_from_time=diff_from,
        diff_from=diff_from,
        diff_to=diff_to,
    )
    await query.execute(db=db)
    return query.get_node_uuids()


def test_diff_count_changes(
    aio_benchmark: Callable[..., Any],
    exec_async: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    branch_with_changes: Branch,
) -> None:
    window: dict[str, Any] = {
        "branch_names": [default_branch.name, branch_with_changes.name],
        "diff_from": Timestamp(branch_with_changes.branched_from),
        "diff_to": Timestamp(),
    }
    counts = exec_async(count_changes, db=db, **window)
    assert counts[branch_with_changes.name] > 0

    aio_benchmark(count_changes, db=db, **window)


def test_diff_field_nodes(
    aio_benchmark: Callable[..., Any],
    exec_async: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    branch_with_changes: Branch,
) -> None:
    window: dict[str, Any] = {
        "base_branch": default_branch,
        "branch": branch_with_changes,
        "diff_from": Timestamp(branch_with_changes.branched_from),
        "diff_to": Timestamp(),
    }
    node_uuids = exec_async(list_field_nodes, db=db, **window)
    assert len(node_uuids) >= TAGS_CHANGED_ON_BRANCH

    aio_benchmark(list_field_nodes, db=db, **window)
