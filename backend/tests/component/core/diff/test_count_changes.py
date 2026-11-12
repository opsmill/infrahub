"""The change count of a time window, checked against a count that reads every edge of the graph.

The count answers two questions: whether an incremental diff update has anything to calculate, and how many
changes a stored diff does not cover yet. Each scenario writes a sequence of changes, records the time between
them, and compares the two counts over every window those times delimit, then over windows that start and end
on the exact time an edge was opened or closed.
"""

from __future__ import annotations

from itertools import combinations, pairwise
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.diff import DiffCountChanges
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.agnostic_edges import create_gadget, create_widget
from tests.helpers.number_pool import add_pool_range, create_range_only_pool
from tests.helpers.schema import TICKET, load_schema
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, BEACON_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

FULL_SCAN_COUNT = """
MATCH (p:Node|Attribute|Relationship)-[diff_rel]-(q)
WHERE diff_rel.branch IN $branch_names
AND (
    (diff_rel.from >= $from_time AND diff_rel.from < $to_time)
    OR (diff_rel.to >= $from_time AND diff_rel.to < $to_time)
)
AND (p.branch_support = "aware" OR q.branch_support = "aware")
RETURN diff_rel.branch AS branch_name, count(*) AS num_changes
"""

EDGE_TIMES = """
MATCH ()-[edge]->()
WHERE edge.branch IN $branch_names
UNWIND [edge.from, edge.to] AS edge_time
WITH DISTINCT edge_time
WHERE edge_time IS NOT NULL
RETURN edge_time
"""

OWNER_SOURCE_AND_RESERVATION_EDGE_TYPES = """
MATCH ()-[edge:HAS_OWNER|HAS_SOURCE|IS_RESERVED]->()
WHERE edge.branch IN $branch_names
RETURN DISTINCT type(edge) AS edge_type
"""


class Timeline:
    """The times recorded between the writes of a scenario."""

    def __init__(self) -> None:
        self.marks: list[Timestamp] = [Timestamp()]

    def mark(self) -> Timestamp:
        self.marks.append(Timestamp())
        return self.marks[-1]

    def windows(self) -> list[tuple[Timestamp, Timestamp]]:
        return list(combinations(self.marks, 2))


async def full_scan_count(
    db: InfrahubDatabase, branch_names: list[str], from_time: Timestamp, to_time: Timestamp
) -> dict[str, int]:
    rows = await db.execute_query(
        query=FULL_SCAN_COUNT,
        params={"branch_names": branch_names, "from_time": from_time.to_string(), "to_time": to_time.to_string()},
        name="test_full_scan_count",
    )
    counts = dict.fromkeys(branch_names, 0)
    counts.update({row["branch_name"]: row["num_changes"] for row in rows})
    return counts


async def indexed_count(
    db: InfrahubDatabase, branch_names: list[str], from_time: Timestamp, to_time: Timestamp
) -> dict[str, int]:
    query = await DiffCountChanges.init(db=db, branch_names=branch_names, diff_from=from_time, diff_to=to_time)
    await query.execute(db=db)
    return query.get_num_changes_by_branch()


async def boundary_windows(
    db: InfrahubDatabase, timeline: Timeline, branch_names: list[str]
) -> list[tuple[Timestamp, Timestamp]]:
    """Consecutive windows whose bounds are the times an edge of these branches was opened or closed.

    Each of those times starts one window and ends the one before it, so an edge is expected in the window
    that starts on its time and not in the window that ends on it.
    """
    rows = await db.execute_query(query=EDGE_TIMES, params={"branch_names": branch_names}, name="test_edge_times")
    first_mark, last_mark = timeline.marks[0], timeline.marks[-1]
    edge_times = sorted(
        edge_time for edge_time in (Timestamp(row["edge_time"]) for row in rows) if first_mark < edge_time < last_mark
    )
    assert len(edge_times) > 0
    return list(pairwise([first_mark, *edge_times, last_mark]))


async def assert_counts_match_in_every_window(
    db: InfrahubDatabase, timeline: Timeline, branch_name_sets: list[list[str]]
) -> dict[str, int]:
    """Compare the two counts over every window of the scenario and return the largest count seen per branch."""
    every_branch_name = sorted({branch_name for branch_names in branch_name_sets for branch_name in branch_names})
    windows = timeline.windows() + await boundary_windows(db=db, timeline=timeline, branch_names=every_branch_name)
    largest: dict[str, int] = {}
    for branch_names in branch_name_sets:
        for from_time, to_time in windows:
            expected = await full_scan_count(db=db, branch_names=branch_names, from_time=from_time, to_time=to_time)
            actual = await indexed_count(db=db, branch_names=branch_names, from_time=from_time, to_time=to_time)
            assert actual == expected, f"{branch_names} from {from_time.to_string()} to {to_time.to_string()}"
            for branch_name, count in actual.items():
                largest[branch_name] = max(largest.get(branch_name, 0), count)
    return largest


def branch_name_sets(default_branch: Branch, *branches: Branch) -> list[list[str]]:
    """The branches a diff asks about, then each of them with the global branch, then one branch on its own."""
    names = [default_branch.name, *[branch.name for branch in branches]]
    return [names, [GLOBAL_BRANCH_NAME, *names], [names[-1]]]


async def test_count_matches_for_attribute_relationship_and_node_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    timeline = Timeline()
    branch = await create_branch(db=db, branch_name="count-changes")
    timeline.mark()

    car_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch, raise_on_error=True)
    car_branch.nbr_seats.value = 2
    car_branch.color.value = "#123456"
    await car_branch.save(db=db)
    timeline.mark()

    # a relationship added, then removed again
    await car_branch.owner.update(db=db, data=person_jane_main)
    await car_branch.save(db=db)
    timeline.mark()
    await car_branch.owner.update(db=db, data=person_john_main)
    await car_branch.save(db=db)
    timeline.mark()

    # a node created and deleted between two marks, so its edges open and close in one window
    person_branch = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person_branch.new(db=db, name="Created and deleted", height=150)
    await person_branch.save(db=db)
    await person_branch.delete(db=db)
    timeline.mark()

    # a node of the default branch deleted on the branch
    camry_branch = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch, raise_on_error=True)
    await camry_branch.delete(db=db)
    timeline.mark()

    john_main = await NodeManager.get_one(db=db, id=person_john_main.id, branch=default_branch, raise_on_error=True)
    john_main.height.value = 190
    await john_main.save(db=db)
    timeline.mark()

    person_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_main.new(db=db, name="Created on the default branch", height=160)
    await person_main.save(db=db)
    timeline.mark()
    await person_main.delete(db=db)
    timeline.mark()

    # nothing is written between the last two marks
    empty_window = (timeline.marks[-1], timeline.mark())

    largest = await assert_counts_match_in_every_window(
        db=db, timeline=timeline, branch_name_sets=branch_name_sets(default_branch, branch)
    )
    assert largest[branch.name] > 0
    assert largest[default_branch.name] > 0
    assert await indexed_count(
        db=db, branch_names=[default_branch.name, branch.name], from_time=empty_window[0], to_time=empty_window[1]
    ) == {default_branch.name: 0, branch.name: 0}


async def test_count_matches_after_a_merge_and_a_rebase(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    timeline = Timeline()
    merged_branch = await create_branch(db=db, branch_name="count-changes-merged")
    rebased_branch = await create_branch(db=db, branch_name="count-changes-rebased")
    timeline.mark()

    car_merged = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=merged_branch, raise_on_error=True)
    car_merged.nbr_seats.value = 7
    await car_merged.owner.update(db=db, data=person_jane_main)
    await car_merged.save(db=db)
    person_merged = await Node.init(db=db, schema="TestPerson", branch=merged_branch)
    await person_merged.new(db=db, name="Created on the merged branch", height=170)
    await person_merged.save(db=db)
    camry_merged = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=merged_branch, raise_on_error=True)
    await camry_merged.delete(db=db)
    timeline.mark()

    john_rebased = await NodeManager.get_one(db=db, id=person_john_main.id, branch=rebased_branch, raise_on_error=True)
    john_rebased.height.value = 175
    await john_rebased.save(db=db)
    person_rebased = await Node.init(db=db, schema="TestPerson", branch=rebased_branch)
    await person_rebased.new(db=db, name="Created on the rebased branch", height=165)
    await person_rebased.save(db=db)
    timeline.mark()

    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=merged_branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=merged_branch)
    timeline.mark()
    merger = await component_registry.get_component(DiffMerger, db=db, branch=merged_branch)
    await merger.merge_graph(at=Timestamp())
    timeline.mark()

    await rebased_branch.rebase(db=db)
    timeline.mark()

    john_rebased = await NodeManager.get_one(db=db, id=person_john_main.id, branch=rebased_branch, raise_on_error=True)
    john_rebased.height.value = 176
    await john_rebased.save(db=db)
    timeline.mark()

    largest = await assert_counts_match_in_every_window(
        db=db, timeline=timeline, branch_name_sets=branch_name_sets(default_branch, merged_branch, rebased_branch)
    )
    assert largest[default_branch.name] > 0
    assert largest[merged_branch.name] > 0
    assert largest[rebased_branch.name] > 0


@pytest.fixture
async def agnostic_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


async def test_count_matches_for_branch_agnostic_fields_and_nodes(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    timeline = Timeline()
    gadget = await create_gadget(db=db, branch=default_branch, name="peer")
    widget = await create_widget(db=db, branch=default_branch, name="on-main", serial=1, gadget=gadget)
    timeline.mark()
    branch = await create_branch(db=db, branch_name="count-changes-agnostic")
    timeline.mark()

    widget_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch, raise_on_error=True)
    widget_branch.name.value = "renamed-on-branch"
    widget_branch.serial.value = 2
    await widget_branch.save(db=db)
    timeline.mark()

    created_on_branch = await create_widget(db=db, branch=branch, name="on-branch", serial=3, gadget=gadget)
    timeline.mark()
    await created_on_branch.delete(db=db)
    timeline.mark()

    beacon = await Node.init(db=db, schema=BEACON_KIND, branch=branch)
    await beacon.new(db=db, name="agnostic-node", serial=4)
    await beacon.save(db=db)
    timeline.mark()
    beacon.serial.value = 5
    await beacon.save(db=db)
    timeline.mark()

    widget_main = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
    await widget_main.delete(db=db)
    timeline.mark()

    largest = await assert_counts_match_in_every_window(
        db=db, timeline=timeline, branch_name_sets=branch_name_sets(default_branch, branch)
    )
    assert largest[branch.name] > 0
    assert largest[default_branch.name] > 0
    assert largest[GLOBAL_BRANCH_NAME] > 0


async def test_count_matches_for_branch_local_nodes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema_branch_local: SchemaBranch,
) -> None:
    timeline = Timeline()
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="Owner", height=180)
    await owner.save(db=db)
    timeline.mark()
    branch = await create_branch(db=db, branch_name="count-changes-local")
    timeline.mark()

    car_branch = await Node.init(db=db, schema="TestCar", branch=branch)
    await car_branch.new(db=db, name="local-on-branch", owner=owner)
    await car_branch.save(db=db)
    timeline.mark()
    car_branch.color.value = "#abcdef"
    await car_branch.save(db=db)
    timeline.mark()

    car_main = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car_main.new(db=db, name="local-on-main", owner=owner)
    await car_main.save(db=db)
    timeline.mark()
    await car_main.delete(db=db)
    timeline.mark()

    owner_branch = await NodeManager.get_one(db=db, id=owner.id, branch=branch, raise_on_error=True)
    owner_branch.height.value = 185
    await owner_branch.save(db=db)
    timeline.mark()

    largest = await assert_counts_match_in_every_window(
        db=db, timeline=timeline, branch_name_sets=branch_name_sets(default_branch, branch)
    )
    assert largest[branch.name] > 0
    assert largest[default_branch.name] > 0


@pytest.fixture
async def ticket_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)


async def test_count_matches_for_owner_source_and_pool_reservation_edges(
    db: InfrahubDatabase, default_branch: Branch, ticket_schema: None
) -> None:
    timeline = Timeline()
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)
    timeline.mark()
    branch = await create_branch(db=db, branch_name="count-changes-lineage")
    timeline.mark()

    # a pool records the number it allocates with an edge on the global branch
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await ticket.new(db=db, title="pooled", ticket_id={"from_pool": {"id": pool.id}})
    await ticket.save(db=db)
    timeline.mark()

    reference = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await reference.new(db=db, title="reference")
    await reference.save(db=db)
    timeline.mark()

    ticket.title.source = reference
    ticket.title.owner = reference
    await ticket.save(db=db)
    timeline.mark()
    ticket.title.clear_source()
    ticket.title.clear_owner()
    await ticket.save(db=db)
    timeline.mark()

    # deleting the only object that holds the number closes the edge of the pool
    await ticket.delete(db=db)
    timeline.mark()

    name_sets = branch_name_sets(default_branch, branch)
    edge_types = await db.execute_query(
        query=OWNER_SOURCE_AND_RESERVATION_EDGE_TYPES,
        params={"branch_names": [GLOBAL_BRANCH_NAME, default_branch.name, branch.name]},
        name="test_edge_types",
    )
    assert {row["edge_type"] for row in edge_types} == {"HAS_OWNER", "HAS_SOURCE", "IS_RESERVED"}

    largest = await assert_counts_match_in_every_window(db=db, timeline=timeline, branch_name_sets=name_sets)
    assert largest[branch.name] > 0
    assert largest[GLOBAL_BRANCH_NAME] > 0
