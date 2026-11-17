"""Run schema migrations twice on one branch and compare the whole graph between the two runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.shared import MigrationInput, SchemaMigration
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import GraphValidationError, collect_graph_violations, verify_graph
from tests.db_snapshot import DbSnapshot, DbSnapshotter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

FIRST_RUN_USER_ID = "first-run-user"
SECOND_RUN_USER_ID = "second-run-user"
USER_BRANCH_NAME = "second-run"
READER_BRANCH_NAME = "second-run-reader"


class BranchKind(StrEnum):
    DEFAULT = "default"
    USER = "user"
    DEFAULT_WITH_READER_BRANCH = "default-with-reader-branch"
    """The migration runs on the default branch while a branch that forked before it still reads the old schema."""


BRANCH_KINDS: list[BranchKind] = [BranchKind.DEFAULT, BranchKind.USER]
AGNOSTIC_BRANCH_KINDS: list[BranchKind] = list(BranchKind)


@dataclass(frozen=True)
class GraphState:
    snapshot: DbSnapshot
    vertex_count: int
    """Counted separately because the snapshot keys vertices by content, so identical vertices collapse."""
    edge_count: int


async def _count(db: InfrahubDatabase, query: str) -> int:
    results = await db.execute_query(query=query)
    return results[0]["count"]


async def read_graph_state(db: InfrahubDatabase) -> GraphState:
    return GraphState(
        snapshot=await DbSnapshotter(db).snapshot(),
        vertex_count=await _count(db=db, query="MATCH (n) RETURN count(n) AS count"),
        edge_count=await _count(db=db, query="MATCH ()-[e]->() RETURN count(e) AS count"),
    )


def _graph_differences(before: GraphState, after: GraphState) -> list[str]:
    differences: list[str] = []
    if before.vertex_count != after.vertex_count:
        differences.append(f"vertex_count: {before.vertex_count} -> {after.vertex_count}")
    if before.edge_count != after.edge_count:
        differences.append(f"edge_count: {before.edge_count} -> {after.edge_count}")
    for label, before_map, after_map in (
        ("vertex", before.snapshot.node_map, after.snapshot.node_map),
        ("edge", before.snapshot.edge_map, after.snapshot.edge_map),
    ):
        differences.extend(f"removed {label}: {before_map[key]}" for key in before_map.keys() - after_map.keys())
        differences.extend(f"added {label}: {after_map[key]}" for key in after_map.keys() - before_map.keys())
    return differences


DATA_VERTEX_LABELS = frozenset({"Node", "Attribute", "Relationship"})


def changed_vertex_uuids(before: GraphState, after: GraphState) -> set[str]:
    """Return the uuid of every Node, Attribute or Relationship vertex that changed or has a changed edge."""
    vertices_by_id = {
        vertex.db_id: vertex for vertex in [*before.snapshot.node_map.values(), *after.snapshot.node_map.values()]
    }
    changed_ids: set[str] = set()
    for before_map, after_map in (
        (before.snapshot.node_map, after.snapshot.node_map),
        (after.snapshot.node_map, before.snapshot.node_map),
    ):
        changed_ids.update(before_map[key].db_id for key in before_map.keys() - after_map.keys())
    for edges, other_edges in (
        (before.snapshot.edge_map, after.snapshot.edge_map),
        (after.snapshot.edge_map, before.snapshot.edge_map),
    ):
        for key in edges.keys() - other_edges.keys():
            changed_ids.update((edges[key].from_db_id, edges[key].to_db_id))
    return {
        vertices_by_id[db_id].properties["uuid"]
        for db_id in changed_ids
        if db_id in vertices_by_id and vertices_by_id[db_id].labels & DATA_VERTEX_LABELS
    }


def assert_graph_unchanged(before: GraphState, after: GraphState) -> None:
    differences = _graph_differences(before=before, after=after)
    assert not differences, "the graph changed:\n" + "\n".join(differences)


async def get_migration_branch(db: InfrahubDatabase, default_branch: Branch, branch_kind: BranchKind) -> Branch:
    """Return the branch to run the migrations on; call it after the data exists on the default branch."""
    if branch_kind is BranchKind.USER:
        return await create_branch(db=db, branch_name=USER_BRANCH_NAME)
    if branch_kind is BranchKind.DEFAULT_WITH_READER_BRANCH:
        await create_branch(db=db, branch_name=READER_BRANCH_NAME)
    return default_branch


async def register_candidate(db: InfrahubDatabase, branch: Branch, candidate: SchemaBranch) -> None:
    """Store the candidate schema on the branch the way a schema load does before its migrations run."""
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    branch.update_schema_hash()
    await branch.save(db=db)


async def run_migrations(
    db: InfrahubDatabase, branch: Branch, migrations: Sequence[SchemaMigration], at: Timestamp, user_id: str
) -> None:
    migration_input = MigrationInput(db=db, at=at, user_id=user_id)
    for migration in migrations:
        result = await migration.execute(migration_input=migration_input, branch=branch)
        assert result.errors == [], f"{migration.name} failed: {result.errors}"


async def assert_second_run_changes_nothing(
    db: InfrahubDatabase, branch: Branch, migrations: Sequence[SchemaMigration], first_run_changes: bool = True
) -> None:
    """Run the migrations twice on the branch and assert that the second run leaves the graph unchanged.

    Each run uses its own timestamp and user, so a write that repeats the same values still changes the graph.

    Raises:
        GraphValidationError: When the first run leaves a graph-integrity violation.

    """
    before_first = await read_graph_state(db=db)
    await run_migrations(db=db, branch=branch, migrations=migrations, at=Timestamp(), user_id=FIRST_RUN_USER_ID)
    after_first = await read_graph_state(db=db)
    if first_run_changes:
        assert _graph_differences(before=before_first, after=after_first), "the first run changed nothing"
    else:
        assert_graph_unchanged(before=before_first, after=after_first)
    # Raised only after the comparison, so a first run that damages the graph still has its second run checked.
    first_run_violations = await collect_graph_violations(db=db)

    await run_migrations(db=db, branch=branch, migrations=migrations, at=Timestamp(), user_id=SECOND_RUN_USER_ID)
    assert_graph_unchanged(before=after_first, after=await read_graph_state(db=db))
    if first_run_violations:
        raise GraphValidationError(violations=first_run_violations)
    await verify_graph(db=db)
