from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@dataclass
class MetadataOrderByCase:
    name: str
    order_by_entry: str
    expected_indices: list[int]


METADATA_ORDER_BY_CASES = [
    MetadataOrderByCase(
        name="created_at_desc",
        order_by_entry="node_metadata__created_at__desc",
        expected_indices=[2, 1, 0],
    ),
    MetadataOrderByCase(
        name="created_at_implicit_asc",
        order_by_entry="node_metadata__created_at",
        expected_indices=[0, 1, 2],
    ),
    MetadataOrderByCase(
        name="created_at_explicit_asc",
        order_by_entry="node_metadata__created_at__asc",
        expected_indices=[0, 1, 2],
    ),
]


async def _make_person_with_cars(
    db: InfrahubDatabase, branch: Branch, schema: SchemaBranch, name: str, count: int
) -> tuple[Node, list[Node]]:
    person_schema = schema.get_node(name="TestPerson", duplicate=False)
    car_schema = schema.get_node(name="TestCar", duplicate=False)

    owner = await Node.init(db=db, branch=branch, schema=person_schema)
    await owner.new(db=db, name=name)
    await owner.save(db=db)

    cars: list[Node] = []
    for idx in range(count):
        car = await Node.init(db=db, branch=branch, schema=car_schema)
        await car.new(db=db, name=f"{name}-car-{idx}", nbr_seats=4, is_electric=False, owner=owner)
        await car.save(db=db)
        cars.append(car)
    return owner, cars


@pytest.mark.parametrize("case", METADATA_ORDER_BY_CASES, ids=lambda c: c.name)
async def test_RelationshipGetListQuery_order_by_metadata_with_direction(
    db: InfrahubDatabase,
    car_person_schema: SchemaBranch,
    branch: Branch,
    case: MetadataOrderByCase,
) -> None:
    car_schema = car_person_schema.get_node(name="TestCar", duplicate=False)
    car_schema.order_by = [case.order_by_entry]

    person_schema = car_person_schema.get_node(name="TestPerson", duplicate=False)
    rel_schema = person_schema.get_relationship("cars")

    owner, cars = await _make_person_with_cars(
        db=db, branch=branch, schema=car_person_schema, name="meta-direction", count=3
    )

    query = await RelationshipGetPeerQuery.init(
        db=db,
        branch=branch,
        at=Timestamp(),
        source=owner,
        schema=rel_schema,
        rel_type=DatabaseEdgeType.IS_RELATED.value,
    )
    await query.execute(db=db)

    peer_ids = [peer.peer_id for peer in query.get_peers()]
    assert peer_ids == [cars[i].id for i in case.expected_indices]


async def test_RelationshipGetListQuery_order_by_metadata_updated_at_desc(
    db: InfrahubDatabase, car_person_schema: SchemaBranch, branch: Branch
) -> None:
    car_schema = car_person_schema.get_node(name="TestCar", duplicate=False)
    car_schema.order_by = ["node_metadata__updated_at__desc"]

    person_schema = car_person_schema.get_node(name="TestPerson", duplicate=False)
    rel_schema = person_schema.get_relationship("cars")

    owner, cars = await _make_person_with_cars(db=db, branch=branch, schema=car_person_schema, name="updated", count=3)

    car0_updated = await NodeManager.get_one(db=db, branch=branch, id=cars[0].id)
    car0_updated.get_attribute("name").value = "updated-car-0-renamed"
    await car0_updated.save(db=db)

    query = await RelationshipGetPeerQuery.init(
        db=db,
        branch=branch,
        at=Timestamp(),
        source=owner,
        schema=rel_schema,
        rel_type=DatabaseEdgeType.IS_RELATED.value,
    )
    await query.execute(db=db)

    peer_ids = [peer.peer_id for peer in query.get_peers()]
    assert peer_ids == [cars[0].id, cars[2].id, cars[1].id]


async def test_RelationshipGetListQuery_order_by_attribute_desc(
    db: InfrahubDatabase, car_person_schema: SchemaBranch, branch: Branch
) -> None:
    car_schema = car_person_schema.get_node(name="TestCar", duplicate=False)
    car_schema.order_by = ["name__value__desc"]

    person_schema = car_person_schema.get_node(name="TestPerson", duplicate=False)
    rel_schema = person_schema.get_relationship("cars")

    owner = await Node.init(db=db, branch=branch, schema=person_schema)
    await owner.new(db=db, name="alpha-owner")
    await owner.save(db=db)

    cars: list[Node] = []
    for car_name in ["alpha-car", "bravo-car", "charlie-car"]:
        car = await Node.init(db=db, branch=branch, schema=car_schema)
        await car.new(db=db, name=car_name, nbr_seats=4, is_electric=False, owner=owner)
        await car.save(db=db)
        cars.append(car)

    query = await RelationshipGetPeerQuery.init(
        db=db,
        branch=branch,
        at=Timestamp(),
        source=owner,
        schema=rel_schema,
        rel_type=DatabaseEdgeType.IS_RELATED.value,
    )
    await query.execute(db=db)

    peer_ids = [peer.peer_id for peer in query.get_peers()]
    assert peer_ids == [cars[2].id, cars[1].id, cars[0].id]


async def test_RelationshipGetListQuery_order_by_uuid_tiebreaker(
    db: InfrahubDatabase, car_person_schema: SchemaBranch, branch: Branch
) -> None:
    car_schema = car_person_schema.get_node(name="TestCar", duplicate=False)
    car_schema.order_by = ["nbr_seats__value__asc"]

    person_schema = car_person_schema.get_node(name="TestPerson", duplicate=False)
    rel_schema = person_schema.get_relationship("cars")

    owner = await Node.init(db=db, branch=branch, schema=person_schema)
    await owner.new(db=db, name="tiebreaker-owner")
    await owner.save(db=db)

    cars: list[Node] = []
    for idx in range(4):
        car = await Node.init(db=db, branch=branch, schema=car_schema)
        await car.new(db=db, name=f"tie-car-{idx}", nbr_seats=2, is_electric=False, owner=owner)
        await car.save(db=db)
        cars.append(car)

    query = await RelationshipGetPeerQuery.init(
        db=db,
        branch=branch,
        at=Timestamp(),
        source=owner,
        schema=rel_schema,
        rel_type=DatabaseEdgeType.IS_RELATED.value,
    )
    await query.execute(db=db)

    peer_ids = [peer.peer_id for peer in query.get_peers()]
    assert peer_ids == sorted(car.id for car in cars)


async def test_RelationshipGetListQuery_order_by_multi_field_mixed_direction(
    db: InfrahubDatabase, car_person_schema: SchemaBranch, branch: Branch
) -> None:
    car_schema = car_person_schema.get_node(name="TestCar", duplicate=False)
    car_schema.order_by = ["nbr_seats__value__desc", "name__value"]

    person_schema = car_person_schema.get_node(name="TestPerson", duplicate=False)
    rel_schema = person_schema.get_relationship("cars")

    owner = await Node.init(db=db, branch=branch, schema=person_schema)
    await owner.new(db=db, name="multi-owner")
    await owner.save(db=db)

    specs = [
        ("alpha-multi-car", 2),
        ("bravo-multi-car", 4),
        ("charlie-multi-car", 2),
        ("delta-multi-car", 4),
    ]
    cars_by_name: dict[str, Node] = {}
    for car_name, seats in specs:
        car = await Node.init(db=db, branch=branch, schema=car_schema)
        await car.new(db=db, name=car_name, nbr_seats=seats, is_electric=False, owner=owner)
        await car.save(db=db)
        cars_by_name[car_name] = car

    query = await RelationshipGetPeerQuery.init(
        db=db,
        branch=branch,
        at=Timestamp(),
        source=owner,
        schema=rel_schema,
        rel_type=DatabaseEdgeType.IS_RELATED.value,
    )
    await query.execute(db=db)

    peer_ids = [peer.peer_id for peer in query.get_peers()]
    assert peer_ids == [
        cars_by_name["bravo-multi-car"].id,
        cars_by_name["delta-multi-car"].id,
        cars_by_name["alpha-multi-car"].id,
        cars_by_name["charlie-multi-car"].id,
    ]


@dataclass
class MixedDirectionWithMetadataCase:
    name: str
    order_by: list[str]
    expected_indices: list[int]


# Creation order: 0=alpha(seats=2), 1=bravo(seats=4), 2=charlie(seats=2), 3=delta(seats=4).
# created_at strictly increases with index.
MIXED_DIRECTION_WITH_METADATA_CASES_REL = [
    MixedDirectionWithMetadataCase(
        name="nbr_seats_desc_then_metadata_created_desc",
        order_by=["nbr_seats__value__desc", "node_metadata__created_at__desc"],
        expected_indices=[3, 1, 2, 0],
    ),
    MixedDirectionWithMetadataCase(
        name="nbr_seats_desc_then_metadata_created_asc",
        order_by=["nbr_seats__value__desc", "node_metadata__created_at"],
        expected_indices=[1, 3, 0, 2],
    ),
    MixedDirectionWithMetadataCase(
        name="metadata_created_desc_then_nbr_seats_asc",
        order_by=["node_metadata__created_at__desc", "nbr_seats__value"],
        expected_indices=[3, 2, 1, 0],
    ),
    MixedDirectionWithMetadataCase(
        name="metadata_created_asc_then_name_desc",
        order_by=["node_metadata__created_at", "name__value__desc"],
        expected_indices=[0, 1, 2, 3],
    ),
]


async def test_RelationshipGetListQuery_order_by_multi_field_mixed_direction_with_metadata(
    db: InfrahubDatabase, car_person_schema: SchemaBranch, branch: Branch
) -> None:
    car_schema = car_person_schema.get_node(name="TestCar", duplicate=False)
    person_schema = car_person_schema.get_node(name="TestPerson", duplicate=False)
    rel_schema = person_schema.get_relationship("cars")

    owner = await Node.init(db=db, branch=branch, schema=person_schema)
    await owner.new(db=db, name="mfm-owner")
    await owner.save(db=db)

    specs = [
        ("alpha-mfm-car", 2),
        ("bravo-mfm-car", 4),
        ("charlie-mfm-car", 2),
        ("delta-mfm-car", 4),
    ]
    cars: list[Node] = []
    for car_name, seats in specs:
        car = await Node.init(db=db, branch=branch, schema=car_schema)
        await car.new(db=db, name=car_name, nbr_seats=seats, is_electric=False, owner=owner)
        await car.save(db=db)
        cars.append(car)

    for case in MIXED_DIRECTION_WITH_METADATA_CASES_REL:
        car_schema.order_by = case.order_by
        query = await RelationshipGetPeerQuery.init(
            db=db,
            branch=branch,
            at=Timestamp(),
            source=owner,
            schema=rel_schema,
            rel_type=DatabaseEdgeType.IS_RELATED.value,
        )
        await query.execute(db=db)
        peer_ids = [peer.peer_id for peer in query.get_peers()]
        assert peer_ids == [cars[i].id for i in case.expected_indices], (
            f"order_by={case.order_by!r} produced wrong order"
        )
