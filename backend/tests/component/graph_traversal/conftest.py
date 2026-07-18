from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipDirection
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.helpers.graph_traversal.builders import BowtieGraph, ShortcutGraph

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _self_referential_vertex_builder(
    db: InfrahubDatabase, branch: Branch
) -> Callable[[str, list[Node] | None], Awaitable[Node]]:
    """Register the self-referential ``TestVertex`` schema and return a ``_vertex(name, links)`` factory.

    ``TestVertex`` has a single bidirectional ``links`` relationship to itself, so a graph of any
    shape can be built by wiring vertices to each other.
    """
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Vertex",
                namespace="Test",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="links",
                        peer="TestVertex",
                        identifier="vertex__vertex",
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                        direction=RelationshipDirection.BIDIR,
                    )
                ],
            )
        ]
    )
    registry.schema.register_schema(schema=schema, branch=branch.name)

    async def _vertex(name: str, links: list[Node] | None = None) -> Node:
        node = await Node.init(db=db, schema="TestVertex", branch=branch)
        await node.new(db=db, name=name, links=links or [])
        await node.save(db=db)
        return node

    return _vertex


@pytest.fixture
async def jack_with_blue_tag(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> tuple[Node, Node]:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, firstname="Jack", lastname="Russell", primary_tag=tag_blue_main)
    await person.save(db=db)
    return person, tag_blue_main


@pytest.fixture
async def three_people_shared_tag(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> tuple[Node, Node, Node, Node]:
    # Three people all linked to the same tag. From p1 to p2 the only simple route is the
    # direct p1 -tag- p2 (depth 2); the only deeper route, p1 -tag- p3 -tag- p2 (depth 4),
    # revisits the shared tag and is therefore a non-simple walk that must be excluded.
    people = []
    for first in ("One", "Two", "Three"):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, firstname=first, lastname="Shared", tags=[tag_blue_main])
        await person.save(db=db)
        people.append(person)
    p1, p2, p3 = people
    return p1, p2, p3, tag_blue_main


@pytest.fixture
async def linked_vertices_with_shortcut(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_schema: None,
    register_core_models_schema: SchemaBranch,
) -> ShortcutGraph:
    # A non-bipartite graph (self-referential ``links``) where the middle is reachable from the
    # source both directly (a shortcut) and via the detour. Combined with middle-bridge-destination
    # this gives a shortest route source -> middle -> bridge -> destination (depth 3) and a longer
    # simple route source -> detour -> middle -> bridge -> destination (depth 4) whose midpoint
    # (the middle) is NOT at its shortest distance — shortest_paths_only=True omits it, =False keeps it.
    make_vertex = _self_referential_vertex_builder(db, default_branch)
    destination = await make_vertex("D")
    bridge = await make_vertex("B", [destination])
    middle = await make_vertex("M", [bridge])
    detour = await make_vertex("A", [middle])
    source = await make_vertex("S", [middle, detour])
    return ShortcutGraph(source=source, detour=detour, middle=middle, bridge=bridge, destination=destination)


@pytest.fixture
async def bowtie_graph(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_schema: None,
    register_core_models_schema: SchemaBranch,
) -> BowtieGraph:
    # source -[links]- {a0,a1,a2} -[links]- hub -[links]- {b0,b1,b2} -[links]- destination.
    # Every depth-4 route funnels through the single hub, so the depth-4 tier joins 3 left halves
    # (all ending at the hub) with 3 right halves (all starting at the hub) into 3x3 = 9 candidate
    # paths — while neither half set alone exceeds a small cap. This isolates the joined-tier cap
    # from the per-half cap. There is no shorter source->destination route.
    make_vertex = _self_referential_vertex_builder(db, default_branch)
    destination = await make_vertex("D")
    b_nodes = [await make_vertex(f"B{i}", [destination]) for i in range(3)]
    hub = await make_vertex("H", b_nodes)
    a_nodes = [await make_vertex(f"A{i}", [hub]) for i in range(3)]
    source = await make_vertex("S", a_nodes)
    return BowtieGraph(source=source, hub=hub, destination=destination)


@pytest.fixture
async def two_ips_in_one_namespace(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> tuple[Node, Node, Node]:
    # An IpamNamespace plus two addresses whose only data link is that namespace.
    namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE, branch=default_branch)
    await namespace.new(db=db, name="traversal-ns", default=False)
    await namespace.save(db=db)

    ip1 = await Node.init(db=db, schema="IpamIPAddress", branch=default_branch)
    await ip1.new(db=db, address="192.0.2.1/32", ip_namespace=namespace)
    await ip1.save(db=db)

    ip2 = await Node.init(db=db, schema="IpamIPAddress", branch=default_branch)
    await ip2.new(db=db, address="192.0.2.2/32", ip_namespace=namespace)
    await ip2.save(db=db)

    return namespace, ip1, ip2


@pytest.fixture
async def person_with_paths_at_two_depths(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> tuple[Node, Node]:
    # person1 reaches the blue tag at depth 1 (primary_tag) and at depth 3
    # (person1 -tags- red -tags- person2 -primary_tag- blue), so a single
    # source/destination pair has paths at two different depths.
    _, blue = jack_with_blue_tag

    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="Red")
    await red.save(db=db)

    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, firstname="Ada", lastname="One", primary_tag=blue, tags=[red])
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, firstname="Bea", lastname="Two", primary_tag=blue, tags=[red])
    await person2.save(db=db)

    return person1, blue


@pytest.fixture
async def car_with_owner_and_driver(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> tuple[Node, Node, Node]:
    # Two distinct persons connected to one car via two relationships with
    # different schema identifiers — so each is independently filterable.
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="Owner", height=170)
    await owner.save(db=db)

    driver = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await driver.new(db=db, name="Driver", height=180)
    await driver.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="Coupe", is_electric=True, nbr_seats=2, color="#ff0000", owner=owner, driver=driver)
    await car.save(db=db)

    return car, owner, driver


@pytest.fixture
async def human_with_two_pets(
    db: InfrahubDatabase, default_branch: Branch, dependent_generics_schema: SchemaBranch
) -> tuple[Node, Node, Node]:
    # One human linked to two animals — one of each concrete implementor of
    # the Animal generic — so excluded_kinds can drop one concrete kind while
    # keeping the other.
    human = await Node.init(db=db, schema="TestHuman", branch=default_branch)
    await human.new(db=db, name="Alice")
    await human.save(db=db)

    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Rex", breed="Labrador", owner=human)
    await dog.save(db=db)

    cat = await Node.init(db=db, schema="TestCat", branch=default_branch)
    await cat.new(db=db, name="Whiskers", breed="Persian", owner=human)
    await cat.save(db=db)

    return human, dog, cat
