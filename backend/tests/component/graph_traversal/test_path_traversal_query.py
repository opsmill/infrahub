import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graph_traversal.path import PathTraversalQuery
from infrahub.graph_traversal.planning.models import Plan, TerminalById, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from tests.helpers.graph_traversal.builders import build_permission_resolver


@pytest.fixture
async def jack_with_blue_tag(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> tuple[Node, Node]:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, firstname="Jack", lastname="Russell", primary_tag=tag_blue_main)
    await person.save(db=db)
    return person, tag_blue_main


def _build_plan(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    source: Node,
    destination: Node,
    max_depth: int = 1,
) -> Plan:
    """Build a Plan exactly as a (future) resolver would.

    Uses a wildcard-allow PermissionResolver to match the pre-refactor "no
    permission filtering" semantics, and an empty ``excluded_namespaces`` so
    the fixture's BuiltinTag destination is reachable (the default exclusions
    include Builtin, which would prune the terminal at BFS time).
    """
    planner = SchemaPlanner(
        schema_branch=db.schema.get_schema_branch(name=branch.name),
        branch=branch,
        permission_resolver=build_permission_resolver(default_branch_name=branch.name),
    )
    return planner.plan(
        source_kind=source.get_kind(),
        terminal_predicate=TerminalById(node_id=destination.id, kind=destination.get_kind()),
        max_depth=max_depth,
        user_filters=UserFilters(excluded_namespaces=frozenset()),
    )


async def test_returns_direct_peer_path_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag

    plan = _build_plan(db=db, branch=default_branch, source=person, destination=tag)
    assert not plan.is_empty, "expected at least one schema hop from TestPerson to BuiltinTag"

    query = await PathTraversalQuery.init(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    paths = query.get_paths()

    assert len(paths) >= 1
    shortest = paths[0]
    assert shortest.depth == 1
    assert shortest.start_node.uuid == person.id
    assert len(shortest.hops) == 1
    assert shortest.hops[-1].node.uuid == tag.id
    assert shortest.hops[-1].relationship_identifier


async def test_returns_direct_peer_path_on_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="feature")

    plan = _build_plan(db=db, branch=feature_branch, source=person, destination=tag)
    assert not plan.is_empty

    query = await PathTraversalQuery.init(
        db=db,
        branch=feature_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    paths = query.get_paths()

    assert len(paths) >= 1
    assert paths[0].depth == 1
    assert paths[0].start_node.uuid == person.id
    assert len(paths[0].hops) == 1
    assert paths[0].hops[-1].node.uuid == tag.id
    assert paths[0].hops[-1].relationship_identifier
