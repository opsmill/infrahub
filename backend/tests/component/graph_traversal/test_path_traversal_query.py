from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graph_traversal.planning.models import Plan, TerminalById, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from tests.helpers.graph_traversal.builders import (
    build_path_traversal_query,
    build_permission_resolver,
    identifier_of,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


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


async def test_returns_direct_peer_path_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag

    plan = _build_plan(db=db, branch=default_branch, source=person, destination=tag)
    assert not plan.is_empty

    query = await build_path_traversal_query(
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

    query = await build_path_traversal_query(
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

    query = await build_path_traversal_query(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    paths = query.get_paths()

    assert paths == []


async def test_default_branch_edge_deleted_on_user_branch_is_hidden(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    """Test query correctly ignored a relationship deleted on a user branch"""
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="feature-edge-deleted")

    person_on_branch = await NodeManager.get_one(db=db, id=person.id, branch=feature_branch)
    assert person_on_branch is not None
    await person_on_branch.get_relationship("primary_tag").update(db=db, data=None)
    await person_on_branch.save(db=db)

    plan = _build_plan(db=db, branch=feature_branch, source=person, destination=tag)
    assert not plan.is_empty

    query = await build_path_traversal_query(
        db=db,
        branch=feature_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    paths = query.get_paths()

    assert paths == [], "deletion on the user branch should mask the default-branch edge"


async def test_default_branch_edge_remains_visible_on_user_branch_when_not_deleted(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    """Test relationship created before branch forked is visible on branch"""
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="feature-untouched")

    plan = _build_plan(db=db, branch=feature_branch, source=person, destination=tag)
    assert not plan.is_empty

    query = await build_path_traversal_query(
        db=db,
        branch=feature_branch,
        plan=plan,
        source_id=person.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    paths = query.get_paths()

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
    owner_query = await build_path_traversal_query(
        db=db,
        branch=default_branch,
        plan=owner_plan,
        source_id=car.id,
        default_branch_name=default_branch.name,
    )
    await owner_query.execute(db=db)
    owner_paths = owner_query.get_paths()
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
    driver_only_to_owner_query = await build_path_traversal_query(
        db=db,
        branch=default_branch,
        plan=driver_only_to_owner_plan,
        source_id=car.id,
        default_branch_name=default_branch.name,
    )
    await driver_only_to_owner_query.execute(db=db)
    assert driver_only_to_owner_query.get_paths() == []

    # And as a positive control: driver identifier with destination=driver returns
    # exactly the driver edge.
    driver_plan = _build_plan(
        db=db,
        branch=default_branch,
        source=car,
        destination=driver,
        user_filters=UserFilters(excluded_namespaces=frozenset(), relationship_filter=frozenset({driver_identifier})),
    )
    driver_query = await build_path_traversal_query(
        db=db,
        branch=default_branch,
        plan=driver_plan,
        source_id=car.id,
        default_branch_name=default_branch.name,
    )
    await driver_query.execute(db=db)
    driver_paths = driver_query.get_paths()
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
    query = await build_path_traversal_query(
        db=db,
        branch=default_branch,
        plan=plan,
        source_id=human.id,
        default_branch_name=default_branch.name,
    )
    await query.execute(db=db)
    paths = query.get_paths()

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
