from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graph_traversal.planning.models import Plan, TerminalById, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from tests.helpers.graph_traversal.builders import (
    build_path_traversal_executor,
    build_permission_resolver,
    identifier_of,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal.results import PathData


def _build_plan(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    source: Node,
    destination: Node,
    max_depth: int = 1,
    user_filters: UserFilters | None = None,
) -> Plan:
    # Default to empty excluded_namespaces — the canonical default set would
    # prune the fixture's terminal, leaving no plan to render.
    planner = SchemaPlanner(
        schema_branch=db.schema.get_schema_branch(name=branch.name),
        branch=branch,
        permission_resolver=build_permission_resolver(default_branch_name=branch.name),
    )
    return planner.plan(
        source_kind=source.get_kind(),
        terminal_predicate=TerminalById(node_id=destination.id, kind=destination.get_kind()),
        max_depth=max_depth,
        user_filters=user_filters if user_filters is not None else UserFilters(excluded_namespaces=frozenset()),
    )


async def _run_paths(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    default_branch_name: str,
    plan: Plan,
    source_id: str,
    max_paths: int = 10,
) -> list[PathData]:
    executor = build_path_traversal_executor(db=db, branch=branch, default_branch_name=default_branch_name)
    return await executor.run(plan=plan, source_id=source_id, max_paths=max_paths)


def _path_signature(path: PathData) -> tuple[int, tuple[str, ...]]:
    """A stable identity for a path: its depth plus the ordered hop-uuid sequence."""
    return (path.depth, tuple(hop.node.uuid for hop in path.hops))


async def test_returns_direct_peer_path_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag

    plan = _build_plan(db=db, branch=default_branch, source=person, destination=tag)
    assert not plan.is_empty

    paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

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

    paths = await _run_paths(
        db=db, branch=feature_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert len(paths) >= 1
    assert paths[0].depth == 1
    assert paths[0].start_node.uuid == person.id
    assert len(paths[0].hops) == 1
    assert paths[0].hops[-1].node.uuid == tag.id
    assert paths[0].hops[-1].relationship_identifier


async def test_user_branch_edge_is_invisible_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> None:
    """Test edges on a user branch are ignored for a query on the default branch"""
    feature_branch = await create_branch(db=db, branch_name="feature-user-only-edge")

    person = await Node.init(db=db, schema="TestPerson", branch=feature_branch)
    await person.new(db=db, firstname="Mira", lastname="Lin", primary_tag=tag_blue_main)
    await person.save(db=db)

    plan = _build_plan(db=db, branch=default_branch, source=person, destination=tag_blue_main)
    assert not plan.is_empty

    paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert paths == []


async def test_default_branch_edge_deleted_on_user_branch_is_hidden(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    """Test query correctly ignores a relationship deleted on a user branch (both BFS halves)"""
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="feature-edge-deleted")

    person_on_branch = await NodeManager.get_one(db=db, id=person.id, branch=feature_branch)
    assert person_on_branch is not None
    await person_on_branch.get_relationship("primary_tag").update(db=db, data=None)
    await person_on_branch.save(db=db)

    plan = _build_plan(db=db, branch=feature_branch, source=person, destination=tag)
    assert not plan.is_empty

    paths = await _run_paths(
        db=db, branch=feature_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert paths == [], "deletion on the user branch should mask the default-branch edge"


async def test_default_branch_edge_remains_visible_on_user_branch_when_not_deleted(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    """Test relationship created before branch forked is visible on branch"""
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="feature-untouched")

    plan = _build_plan(db=db, branch=feature_branch, source=person, destination=tag)
    assert not plan.is_empty

    paths = await _run_paths(
        db=db, branch=feature_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert len(paths) == 1
    only = paths[0]
    assert only.depth == 1
    assert only.start_node.uuid == person.id
    assert [hop.node.uuid for hop in only.hops] == [tag.id]


async def test_relationship_filter_selects_one_of_two_parallel_relationships(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    # Two distinct schema-level relationships connect TestCar to TestPerson.
    # relationship_filter must narrow the path to the chosen identifier.
    car, owner, driver = car_with_owner_and_driver
    owner_identifier = identifier_of(db=db, branch=default_branch, kind="TestCar", relationship="owner")
    driver_identifier = identifier_of(db=db, branch=default_branch, kind="TestCar", relationship="driver")
    assert owner_identifier != driver_identifier

    owner_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        destination=owner,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({owner_identifier})),
    )
    owner_paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=owner_plan, source_id=car.id
    )
    assert len(owner_paths) == 1
    assert owner_paths[0].hops[-1].node.uuid == owner.id
    assert owner_paths[0].hops[-1].relationship_identifier == owner_identifier

    # Filtering to the driver identifier with destination=owner produces no
    # path: the planner allows the hop schema-wise, but no data edge with the
    # driver identifier reaches the owner node.
    driver_only_to_owner_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        destination=owner,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({driver_identifier})),
    )
    driver_only_to_owner_paths = await _run_paths(
        db=db,
        branch=default_branch,
        default_branch_name=default_branch.name,
        plan=driver_only_to_owner_plan,
        source_id=car.id,
    )
    assert driver_only_to_owner_paths == []

    # And as a positive control: driver identifier with destination=driver returns
    # exactly the driver edge.
    driver_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        destination=driver,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({driver_identifier})),
    )
    driver_paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=driver_plan, source_id=car.id
    )
    assert len(driver_paths) == 1
    assert driver_paths[0].hops[-1].node.uuid == driver.id
    assert driver_paths[0].hops[-1].relationship_identifier == driver_identifier


async def test_kind_filter_accepts_generic_terminal(
    db: InfrahubDatabase, default_branch: Branch, human_with_two_pets: tuple[Node, Node, Node]
) -> None:
    # Source is a concrete kind; destination is a concrete implementor of a
    # generic. Passing the generic into kind_filter must still admit the
    # concrete destination
    human, dog, _cat = human_with_two_pets

    plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        destination=dog,
        user_filters=UserFilters(excluded_namespaces=frozenset(), kind_filter=frozenset({"TestAnimal"})),
    )
    paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=human.id
    )

    assert len(paths) == 1
    only = paths[0]
    assert only.depth == 1
    assert only.start_node.uuid == human.id
    assert [hop.node.uuid for hop in only.hops] == [dog.id]


async def test_excluded_kinds_with_generic_drops_all_concrete_implementors(
    db: InfrahubDatabase, default_branch: Branch, human_with_two_pets: tuple[Node, Node, Node]
) -> None:
    # The destination is a concrete implementor of the excluded generic, so
    # the plan must come out empty.
    human, dog, _cat = human_with_two_pets

    plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        destination=dog,
        user_filters=UserFilters(excluded_namespaces=frozenset(), excluded_kinds=frozenset({"TestAnimal"})),
    )
    assert plan.is_empty


async def test_default_excluded_kinds_hide_ipam_namespace_bounce(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_ips_in_one_namespace: tuple[Node, Node, Node],
) -> None:
    # Two IPs share only their namespace; the namespace-kind default exclusion
    # must remove the IP > namespace > IP' bounce while the prefix route keeps
    # the plan renderable.
    _namespace, ip1, ip2 = two_ips_in_one_namespace

    plan = _build_plan(
        db=db,
        branch=default_branch,
        source=ip1,
        destination=ip2,
        max_depth=2,
        user_filters=UserFilters(),
    )
    assert "IpamNamespace" in plan.excluded_kinds
    assert not plan.is_empty

    paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=ip1.id
    )

    assert paths == []


async def test_included_kinds_re_include_ipam_namespace_bounce(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_ips_in_one_namespace: tuple[Node, Node, Node],
) -> None:
    # Re-including the namespace kind restores the bounce path, proving the
    # default behavior is an exclusion rather than absence of data.
    namespace, ip1, ip2 = two_ips_in_one_namespace

    plan = _build_plan(
        db=db,
        branch=default_branch,
        source=ip1,
        destination=ip2,
        max_depth=2,
        user_filters=UserFilters(included_kinds=frozenset({"IpamNamespace"})),
    )
    assert "IpamNamespace" not in plan.excluded_kinds

    paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=ip1.id
    )

    assert len(paths) == 1
    assert paths[0].depth == 2
    assert [hop.node.uuid for hop in paths[0].hops] == [namespace.id, ip2.id]


async def test_executor_returns_shortest_first_across_depths(
    db: InfrahubDatabase, default_branch: Branch, person_with_paths_at_two_depths: tuple[Node, Node]
) -> None:
    person1, blue = person_with_paths_at_two_depths
    plan = _build_plan(db=db, branch=default_branch, source=person1, destination=blue, max_depth=3)
    assert not plan.is_empty

    paths = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )

    assert [p.depth for p in paths] == [1, 3]


async def test_executor_respects_max_paths(
    db: InfrahubDatabase, default_branch: Branch, person_with_paths_at_two_depths: tuple[Node, Node]
) -> None:
    person1, blue = person_with_paths_at_two_depths
    plan = _build_plan(db=db, branch=default_branch, source=person1, destination=blue, max_depth=3)
    assert not plan.is_empty

    paths = await _run_paths(
        db=db,
        branch=default_branch,
        default_branch_name=default_branch.name,
        plan=plan,
        source_id=person1.id,
        max_paths=1,
    )

    assert len(paths) == 1
    assert paths[0].depth == 1
    assert paths[0].start_node.uuid == person1.id
    assert [hop.node.uuid for hop in paths[0].hops] == [blue.id]


async def _person_with_two_paths_at_depth_three(db: InfrahubDatabase, branch: Branch, blue: Node) -> Node:
    """Source person reaching ``blue`` directly (depth 1) and via two depth-3 routes.

    ``person1 -tags- {red, green}``; both tags are also on ``person2``, which has
    ``blue`` as its primary tag. So ``person1 → blue`` has one depth-1 path
    (primary_tag) and two distinct depth-3 paths (through ``red`` and through
    ``green``) — a tier with more than one path, for cap/ordering coverage.
    """
    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=branch)
    await red.new(db=db, name="Red")
    await red.save(db=db)
    green = await Node.init(db=db, schema=InfrahubKind.TAG, branch=branch)
    await green.new(db=db, name="Green")
    await green.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person2.new(db=db, firstname="Bea", lastname="Two", primary_tag=blue, tags=[red, green])
    await person2.save(db=db)

    person1 = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person1.new(db=db, firstname="Ada", lastname="One", primary_tag=blue, tags=[red, green])
    await person1.save(db=db)
    return person1


async def test_increasing_max_paths_only_appends_paths(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> None:
    """Raising the cap must only add paths."""
    person1 = await _person_with_two_paths_at_depth_three(db=db, branch=default_branch, blue=tag_blue_main)
    plan = _build_plan(db=db, branch=default_branch, source=person1, destination=tag_blue_main, max_depth=3)
    assert not plan.is_empty

    results: dict[int, list[tuple[int, tuple[str, ...]]]] = {}
    for cap in (1, 2, 3):
        paths = await _run_paths(
            db=db,
            branch=default_branch,
            default_branch_name=default_branch.name,
            plan=plan,
            source_id=person1.id,
            max_paths=cap,
        )
        assert len(paths) == cap
        results[cap] = [_path_signature(p) for p in paths]

    # depth-ascending, and each cap is a strict prefix of the next
    assert results[1] == results[2][:1] == results[3][:1]
    assert results[2] == results[3][:2]
    assert results[1][0][0] == 1, "the single shortest path is the depth-1 direct edge"
    assert {sig[0] for sig in results[3]} == {1, 3}, "depth-1 path plus two depth-3 paths"


async def test_result_is_deterministic_across_runs(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> None:
    """Same query + same data → identical ordered output."""
    person1 = await _person_with_two_paths_at_depth_three(db=db, branch=default_branch, blue=tag_blue_main)
    plan = _build_plan(db=db, branch=default_branch, source=person1, destination=tag_blue_main, max_depth=3)

    first = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )
    second = await _run_paths(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )

    assert [_path_signature(p) for p in first] == [_path_signature(p) for p in second]
