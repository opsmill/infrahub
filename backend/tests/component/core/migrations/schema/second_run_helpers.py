"""Run schema migrations twice on one branch and compare the whole graph between the two runs."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import GraphValidationError, collect_graph_violations, verify_graph
from tests.db_snapshot import DbSnapshotter

if TYPE_CHECKING:
    from collections import Counter
    from collections.abc import Mapping, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.shared import SchemaMigration
    from infrahub.database import InfrahubDatabase
    from tests.db_snapshot import DbEdge, DbNode, DbSnapshot

FIRST_RUN_USER_ID = "first-run-user"
SECOND_RUN_USER_ID = "second-run-user"
USER_BRANCH_NAME = "second-run"
READER_BRANCH_NAME = "second-run-reader"
DATA_VERTEX_LABELS = frozenset({"Node", "Attribute", "Relationship"})


class BranchKind(StrEnum):
    DEFAULT = "default"
    USER = "user"
    DEFAULT_WITH_READER_BRANCH = "default-with-reader-branch"
    """The migration runs on the default branch while a branch that forked before it still reads the field."""


BRANCH_KINDS: list[BranchKind] = [BranchKind.DEFAULT, BranchKind.USER]
AGNOSTIC_BRANCH_KINDS: list[BranchKind] = list(BranchKind)


class SecondRunChangedGraphError(AssertionError):
    """Raised when the second run of the migrations changes the graph."""


class SecondRunReportedWorkError(AssertionError):
    """Raised when the second run leaves the graph unchanged but reports migrations executed."""


async def read_graph_state(db: InfrahubDatabase) -> DbSnapshot:
    return await DbSnapshotter(db).snapshot()


def _element_differences(
    label: str,
    before_map: Mapping[int, DbNode | DbEdge],
    before_counts: Counter[int],
    after_map: Mapping[int, DbNode | DbEdge],
    after_counts: Counter[int],
) -> list[str]:
    differences = []
    for key in before_counts.keys() | after_counts.keys():
        if before_counts[key] != after_counts[key]:
            element = after_map[key] if key in after_map else before_map[key]
            differences.append(f"{label} {before_counts[key]} -> {after_counts[key]}: {element}")
    return differences


def graph_differences(before: DbSnapshot, after: DbSnapshot) -> list[str]:
    """Describe every vertex and edge whose number of copies differs between the two snapshots."""
    return _element_differences(
        "vertex", before.node_map, before.node_counts, after.node_map, after.node_counts
    ) + _element_differences("edge", before.edge_map, before.edge_counts, after.edge_map, after.edge_counts)


def assert_graph_unchanged(before: DbSnapshot, after: DbSnapshot) -> None:
    differences = graph_differences(before=before, after=after)
    assert not differences, "the graph changed:\n" + "\n".join(differences)


def changed_vertex_uuids(before: DbSnapshot, after: DbSnapshot) -> set[str]:
    """Return the uuid of every Node, Attribute or Relationship vertex that changed or has a changed edge."""
    vertices_by_id = {vertex.db_id: vertex for vertex in [*before.node_map.values(), *after.node_map.values()]}
    changed_ids: set[str] = set()
    for nodes, other_nodes in ((before.node_map, after.node_map), (after.node_map, before.node_map)):
        changed_ids.update(nodes[key].db_id for key in nodes.keys() - other_nodes.keys())
    for edges, other_edges in ((before.edge_map, after.edge_map), (after.edge_map, before.edge_map)):
        for key in edges.keys() - other_edges.keys():
            changed_ids.update((edges[key].from_db_id, edges[key].to_db_id))
    return {
        vertices_by_id[db_id].properties["uuid"]
        for db_id in changed_ids
        if db_id in vertices_by_id and vertices_by_id[db_id].labels & DATA_VERTEX_LABELS
    }


async def get_migration_branch(db: InfrahubDatabase, default_branch: Branch, branch_kind: BranchKind) -> Branch:
    """Return the branch to run the migrations on; call it after the data exists on the default branch."""
    if branch_kind is BranchKind.USER:
        return await create_branch(db=db, branch_name=USER_BRANCH_NAME)
    if branch_kind is BranchKind.DEFAULT_WITH_READER_BRANCH:
        await create_branch(db=db, branch_name=READER_BRANCH_NAME)
    return default_branch


async def run_migrations(
    db: InfrahubDatabase, branch: Branch, migrations: Sequence[SchemaMigration], at: Timestamp, user_id: str
) -> int:
    """Run the migrations in order and return the number of migrations they report executed."""
    migration_input = MigrationInput(db=db, at=at, user_id=user_id)
    executed = 0
    for migration in migrations:
        result = await migration.execute(migration_input=migration_input, branch=branch)
        assert result.errors == [], f"{migration.name} failed: {result.errors}"
        executed += result.nbr_migrations_executed
    return executed


async def assert_second_run_changes_nothing(
    db: InfrahubDatabase, branch: Branch, migrations: Sequence[SchemaMigration], first_run_changes: bool = True
) -> None:
    """Run the migrations twice on the branch and assert that the second run leaves the graph unchanged.

    Each run uses its own timestamp and user, so a write that repeats the same values still changes the graph.

    Raises:
        SecondRunChangedGraphError: When the second run changes the graph.
        SecondRunReportedWorkError: When the second run reports migrations executed.
        GraphValidationError: When the first run leaves a graph-integrity violation.

    """
    before_first = await read_graph_state(db=db)
    await run_migrations(db=db, branch=branch, migrations=migrations, at=Timestamp(), user_id=FIRST_RUN_USER_ID)
    after_first = await read_graph_state(db=db)
    if first_run_changes:
        assert graph_differences(before=before_first, after=after_first), "the first run changed nothing"
    else:
        assert_graph_unchanged(before=before_first, after=after_first)
    # Raised only after the comparison, so a first run that damages the graph still has its second run checked.
    first_run_violations = await collect_graph_violations(db=db)

    second_run_executed = await run_migrations(
        db=db, branch=branch, migrations=migrations, at=Timestamp(), user_id=SECOND_RUN_USER_ID
    )
    differences = graph_differences(before=after_first, after=await read_graph_state(db=db))
    if differences:
        raise SecondRunChangedGraphError("the second run changed the graph:\n" + "\n".join(differences))
    if second_run_executed:
        raise SecondRunReportedWorkError(f"the second run reported {second_run_executed} migrations executed")
    if first_run_violations:
        raise GraphValidationError(violations=first_run_violations)
    await verify_graph(db=db)
