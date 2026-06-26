from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graph_traversal.planning.models import Plan, TerminalByKinds, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from tests.helpers.graph_traversal.builders import build_permission_resolver, build_reachable_executor, identifier_of

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal.reachable import ReachableNodeData


def _build_plan(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    source: Node,
    target_kinds: frozenset[str],
    max_depth: int = 2,
    user_filters: UserFilters | None = None,
) -> Plan:
    # Default to empty excluded_namespaces — the canonical default set would
    # prune the fixture's terminal kinds, leaving no plan to render.
    planner = SchemaPlanner(
        schema_branch=db.schema.get_schema_branch(name=branch.name),
        branch=branch,
        permission_resolver=build_permission_resolver(default_branch_name=branch.name),
    )
    return planner.plan(
        source_kind=source.get_kind(),
        terminal_predicate=TerminalByKinds(kinds=target_kinds),
        max_depth=max_depth,
        user_filters=user_filters if user_filters is not None else UserFilters(excluded_namespaces=frozenset()),
    )


async def _reachable_nodes(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    default_branch_name: str,
    plan: Plan,
    source_id: str,
    max_targets: int = 50,
    max_paths: int = 500,
    shortest_paths_only: bool = True,
) -> list[ReachableNodeData]:
    executor = build_reachable_executor(db=db, branch=branch, default_branch_name=default_branch_name)
    return await executor.run(
        plan=plan,
        source_id=source_id,
        max_targets=max_targets,
        max_paths=max_paths,
        shortest_paths_only=shortest_paths_only,
    )


async def test_returns_reachable_target_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag

    plan = _build_plan(db=db, branch=default_branch, source=person, target_kinds=frozenset({tag.get_kind()}))
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert len(results) == 1
    only = results[0]
    assert only.node.uuid == tag.id
    assert only.node.kind == tag.get_kind()
    assert only.depth == 1
    assert only.path.start_node.uuid == person.id
    assert [hop.node.uuid for hop in only.path.hops] == [tag.id]


async def test_user_branch_edge_does_not_surface_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> None:
    # Source and connecting edge created on a user branch. Default-branch
    # traversal must not see the user-branch-only target.
    feature_branch = await create_branch(db=db, branch_name="reach-user-only-edge")

    person = await Node.init(db=db, schema="TestPerson", branch=feature_branch)
    await person.new(db=db, firstname="Mira", lastname="Lin", primary_tag=tag_blue_main)
    await person.save(db=db)

    plan = _build_plan(db=db, branch=default_branch, source=person, target_kinds=frozenset({tag_blue_main.get_kind()}))
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert results == []


async def test_default_branch_target_is_hidden_when_edge_deleted_on_user_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    # Edge active on default branch; deleted on a user branch. The user-branch
    # query must drop the target the deleted edge led to.
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="reach-edge-deleted")

    person_on_branch = await NodeManager.get_one(db=db, id=person.id, branch=feature_branch)
    assert person_on_branch is not None
    await person_on_branch.get_relationship(name="primary_tag").update(db=db, data=None)
    await person_on_branch.save(db=db)

    plan = _build_plan(db=db, branch=feature_branch, source=person, target_kinds=frozenset({tag.get_kind()}))
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=feature_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert results == []


async def test_default_branch_target_remains_visible_on_untouched_user_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="reach-untouched")

    plan = _build_plan(db=db, branch=feature_branch, source=person, target_kinds=frozenset({tag.get_kind()}))
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=feature_branch, default_branch_name=default_branch.name, plan=plan, source_id=person.id
    )

    assert len(results) == 1
    only = results[0]
    assert only.node.uuid == tag.id
    assert only.node.kind == tag.get_kind()
    assert only.depth == 1
    assert [hop.node.uuid for hop in only.path.hops] == [tag.id]


async def test_relationship_filter_selects_one_of_two_parallel_relationships(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    # Without any filter both peers reach via the two distinct identifiers;
    # restricting to one identifier must collapse the result to that peer.
    car, owner, driver = car_with_owner_and_driver
    owner_identifier = identifier_of(db=db, branch=default_branch, kind="TestCar", relationship="owner")
    driver_identifier = identifier_of(db=db, branch=default_branch, kind="TestCar", relationship="driver")
    assert owner_identifier != driver_identifier

    baseline_plan = _build_plan(
        db=db, branch=default_branch, source=car, target_kinds=frozenset({"TestPerson"}), max_depth=1
    )
    baseline = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=baseline_plan, source_id=car.id
    )
    assert {r.node.uuid for r in baseline} == {owner.id, driver.id}

    owner_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        target_kinds=frozenset({"TestPerson"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({owner_identifier})),
    )
    owner_only = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=owner_only_plan, source_id=car.id
    )
    assert {r.node.uuid for r in owner_only} == {owner.id}

    driver_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        target_kinds=frozenset({"TestPerson"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({driver_identifier})),
    )
    driver_only = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=driver_only_plan, source_id=car.id
    )
    assert {r.node.uuid for r in driver_only} == {driver.id}


async def test_excluded_kinds_drops_one_concrete_generic_implementor(
    db: InfrahubDatabase,
    default_branch: Branch,
    human_with_two_pets: tuple[Node, Node, Node],
) -> None:
    # TestAnimal generic is implemented by TestDog and TestCat. Excluding
    # TestCat must leave a path to the Dog and remove the Cat
    human, dog, cat = human_with_two_pets

    baseline_plan = _build_plan(
        db=db, branch=default_branch, source=human, target_kinds=frozenset({"TestDog", "TestCat"}), max_depth=1
    )
    baseline = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=baseline_plan, source_id=human.id
    )
    assert {r.node.uuid for r in baseline} == {dog.id, cat.id}

    dog_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        target_kinds=frozenset({"TestDog", "TestCat"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), excluded_kinds=frozenset({"TestCat"})),
    )
    dog_only = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=dog_only_plan, source_id=human.id
    )
    assert {r.node.uuid for r in dog_only} == {dog.id}

    cat_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        target_kinds=frozenset({"TestDog", "TestCat"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), excluded_kinds=frozenset({"TestDog"})),
    )
    cat_only = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=cat_only_plan, source_id=human.id
    )
    assert {r.node.uuid for r in cat_only} == {cat.id}


async def test_target_kinds_accepts_generic_and_expands_to_concretes(
    db: InfrahubDatabase,
    default_branch: Branch,
    human_with_two_pets: tuple[Node, Node, Node],
) -> None:
    # A user that names the generic should reach every concrete implementor.
    human, dog, cat = human_with_two_pets

    plan = _build_plan(db=db, branch=default_branch, source=human, target_kinds=frozenset({"TestAnimal"}), max_depth=1)
    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=human.id
    )
    assert {r.node.uuid for r in results} == {dog.id, cat.id}


async def test_excluded_kinds_accepts_generic_and_removes_every_concrete_implementor(
    db: InfrahubDatabase,
    default_branch: Branch,
    human_with_two_pets: tuple[Node, Node, Node],
) -> None:
    # Excluding the generic must drop every concrete implementor.
    human, _dog, _cat = human_with_two_pets

    plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        target_kinds=frozenset({"TestDog", "TestCat"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), excluded_kinds=frozenset({"TestAnimal"})),
    )
    assert plan.is_empty


async def test_shortest_mode_returns_only_shortest_path_per_target(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_with_paths_at_two_depths: tuple[Node, Node],
) -> None:
    # The blue tag is reachable from person1 at depth 1 (primary_tag) and depth 3
    # (via the shared red tag + person2). Shortest mode must keep only the depth-1 path.
    person1, blue = person_with_paths_at_two_depths

    plan = _build_plan(
        db=db, branch=default_branch, source=person1, target_kinds=frozenset({blue.get_kind()}), max_depth=3
    )
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )
    blue_entries = [r for r in results if r.node.uuid == blue.id]
    assert len(blue_entries) == 1
    assert blue_entries[0].depth == 1


async def test_all_paths_mode_returns_paths_at_every_depth(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_with_paths_at_two_depths: tuple[Node, Node],
) -> None:
    # Same data, shortest_paths_only=False: every path to blue within max_depth is returned,
    # so blue appears at both depth 1 and depth 3.
    person1, blue = person_with_paths_at_two_depths

    plan = _build_plan(
        db=db, branch=default_branch, source=person1, target_kinds=frozenset({blue.get_kind()}), max_depth=3
    )
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db,
        branch=default_branch,
        default_branch_name=default_branch.name,
        plan=plan,
        source_id=person1.id,
        shortest_paths_only=False,
    )
    blue_depths = sorted({r.depth for r in results if r.node.uuid == blue.id})
    assert blue_depths == [1, 3]


async def test_shortest_mode_reroutes_when_branch_deletes_shortest_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_with_paths_at_two_depths: tuple[Node, Node],
) -> None:
    # Deleting the depth-1 primary_tag edge on a user branch must be respected
    # the shortest result then routes to the depth-3 path
    # exercises intermediate-hop predicates.
    person1, blue = person_with_paths_at_two_depths
    feature_branch = await create_branch(db=db, branch_name="reach-shortest-deleted")

    person1_on_branch = await NodeManager.get_one(db=db, id=person1.id, branch=feature_branch)
    assert person1_on_branch is not None
    await person1_on_branch.get_relationship(name="primary_tag").update(db=db, data=None)
    await person1_on_branch.save(db=db)

    plan = _build_plan(
        db=db, branch=feature_branch, source=person1, target_kinds=frozenset({blue.get_kind()}), max_depth=3
    )
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=feature_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )
    blue_entries = [r for r in results if r.node.uuid == blue.id]
    assert len(blue_entries) >= 1
    assert min(e.depth for e in blue_entries) == 3


async def test_shortest_mode_resolves_each_target_at_its_own_minimum_depth(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> None:
    # Several targets of the same kind, each first reachable at a different depth:
    #   blue  -> depth 1 (person1 -primary_tag- blue)
    #   red   -> depth 1 (person1 -tags- red)
    #   green -> depth 3 (person1 -tags- red -tags- person2 -primary_tag- green)
    # The depth-banded walk must return each at its own minimum depth in one query, dropping
    # each target from deeper bands once it is reached.
    blue = tag_blue_main

    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="Red")
    await red.save(db=db)

    green = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await green.new(db=db, name="Green")
    await green.save(db=db)

    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, firstname="Ada", lastname="One", primary_tag=blue, tags=[red])
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, firstname="Bea", lastname="Two", primary_tag=green, tags=[red])
    await person2.save(db=db)

    plan = _build_plan(
        db=db, branch=default_branch, source=person1, target_kinds=frozenset({blue.get_kind()}), max_depth=3
    )
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )

    depths_by_tag: dict[str, set[int]] = {}
    for r in results:
        depths_by_tag.setdefault(r.node.uuid, set()).add(r.depth)
    assert depths_by_tag.get(blue.id) == {1}
    assert depths_by_tag.get(red.id) == {1}
    assert depths_by_tag.get(green.id) == {3}


async def test_shortest_mode_returns_all_tied_shortest_paths_to_a_target(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None
) -> None:
    # person2 is reachable from person1 only at depth 2, but via two distinct intermediate
    # tags shared by both people. Shortest mode must return BOTH tied depth-2 paths -- the
    # per-band query yields every path at the target's minimum depth, not just one.
    red_a = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red_a.new(db=db, name="RedA")
    await red_a.save(db=db)

    red_b = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red_b.new(db=db, name="RedB")
    await red_b.save(db=db)

    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, firstname="Ada", lastname="One", tags=[red_a, red_b])
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, firstname="Bea", lastname="Two", tags=[red_a, red_b])
    await person2.save(db=db)

    plan = _build_plan(
        db=db, branch=default_branch, source=person1, target_kinds=frozenset({"TestPerson"}), max_depth=2
    )
    assert not plan.is_empty

    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=person1.id
    )

    person2_entries = [r for r in results if r.node.uuid == person2.id]
    assert len(person2_entries) == 2
    assert {e.depth for e in person2_entries} == {2}
    # the two tied paths differ only by their intermediate tag
    assert {e.path.hops[0].node.uuid for e in person2_entries} == {red_a.id, red_b.id}


async def test_kind_filter_accepts_generic_and_admits_every_concrete_implementor(
    db: InfrahubDatabase,
    default_branch: Branch,
    human_with_two_pets: tuple[Node, Node, Node],
) -> None:
    # kind_filter applies to intermediate kinds, but only one hop is needed
    # here, so this exercises the schema-level expansion: every concrete kind
    # behind the generic is admitted as a target peer.
    human, dog, cat = human_with_two_pets

    plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        target_kinds=frozenset({"TestDog", "TestCat"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), kind_filter=frozenset({"TestAnimal"})),
    )
    results = await _reachable_nodes(
        db=db, branch=default_branch, default_branch_name=default_branch.name, plan=plan, source_id=human.id
    )
    assert {r.node.uuid for r in results} == {dog.id, cat.id}
