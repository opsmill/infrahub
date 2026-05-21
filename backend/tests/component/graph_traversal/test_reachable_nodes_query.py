from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graph_traversal.planning.models import Plan, TerminalByKinds, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from infrahub.graph_traversal.reachable import ReachableNodesQuery
from tests.helpers.graph_traversal.builders import build_permission_resolver, identifier_of

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


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


async def test_returns_reachable_target_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag

    plan = _build_plan(db=db, branch=default_branch, source=person, target_kinds=frozenset({tag.get_kind()}))
    assert not plan.is_empty

    query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    results = query.get_reachable_nodes()

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

    query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    results = query.get_reachable_nodes()

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

    query = await ReachableNodesQuery.init(
        db=db,
        branch=feature_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    results = query.get_reachable_nodes()

    assert results == []


async def test_default_branch_target_remains_visible_on_untouched_user_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="reach-untouched")

    plan = _build_plan(db=db, branch=feature_branch, source=person, target_kinds=frozenset({tag.get_kind()}))
    assert not plan.is_empty

    query = await ReachableNodesQuery.init(
        db=db,
        branch=feature_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    results = query.get_reachable_nodes()

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
    baseline_query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=baseline_plan,
        source_id=car.id,
        default_branch_name=default_branch.name,
    )
    await baseline_query.execute(db=db)
    baseline_ids = {r.node.uuid for r in baseline_query.get_reachable_nodes()}
    assert baseline_ids == {owner.id, driver.id}

    owner_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        target_kinds=frozenset({"TestPerson"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({owner_identifier})),
    )
    owner_only_query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=owner_only_plan,
        source_id=car.id,
        default_branch_name=default_branch.name,
    )
    await owner_only_query.execute(db=db)
    owner_only_ids = {r.node.uuid for r in owner_only_query.get_reachable_nodes()}
    assert owner_only_ids == {owner.id}

    driver_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        target_kinds=frozenset({"TestPerson"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({driver_identifier})),
    )
    driver_only_query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=driver_only_plan,
        source_id=car.id,
        default_branch_name=default_branch.name,
    )
    await driver_only_query.execute(db=db)
    driver_only_ids = {r.node.uuid for r in driver_only_query.get_reachable_nodes()}
    assert driver_only_ids == {driver.id}


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
    baseline_query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=baseline_plan,
        source_id=human.id,
        default_branch_name=default_branch.name,
    )
    await baseline_query.execute(db=db)
    baseline_ids = {r.node.uuid for r in baseline_query.get_reachable_nodes()}
    assert baseline_ids == {dog.id, cat.id}

    dog_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        target_kinds=frozenset({"TestDog", "TestCat"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), excluded_kinds=frozenset({"TestCat"})),
    )
    dog_only_query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=dog_only_plan,
        source_id=human.id,
        default_branch_name=default_branch.name,
    )
    await dog_only_query.execute(db=db)
    dog_only_ids = {r.node.uuid for r in dog_only_query.get_reachable_nodes()}
    assert dog_only_ids == {dog.id}

    cat_only_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=human,
        target_kinds=frozenset({"TestDog", "TestCat"}),
        max_depth=1,
        user_filters=UserFilters(excluded_namespaces=frozenset(), excluded_kinds=frozenset({"TestDog"})),
    )
    cat_only_query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=cat_only_plan,
        source_id=human.id,
        default_branch_name=default_branch.name,
    )
    await cat_only_query.execute(db=db)
    cat_only_ids = {r.node.uuid for r in cat_only_query.get_reachable_nodes()}
    assert cat_only_ids == {cat.id}


async def test_target_kinds_accepts_generic_and_expands_to_concretes(
    db: InfrahubDatabase,
    default_branch: Branch,
    human_with_two_pets: tuple[Node, Node, Node],
) -> None:
    # A user that names the generic should reach every concrete implementor.
    human, dog, cat = human_with_two_pets

    plan = _build_plan(db=db, branch=default_branch, source=human, target_kinds=frozenset({"TestAnimal"}), max_depth=1)
    query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=human.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    ids = {r.node.uuid for r in query.get_reachable_nodes()}
    assert ids == {dog.id, cat.id}


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
    query = await ReachableNodesQuery.init(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=human.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    ids = {r.node.uuid for r in query.get_reachable_nodes()}
    assert ids == {dog.id, cat.id}
