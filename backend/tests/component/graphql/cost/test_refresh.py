from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.cost.collector import StatisticsCollector
from infrahub.graphql.cost.constants import STATISTICS_POINTER_KEY
from infrahub.graphql.cost.models import HistogramBucket, KindStatistics, RelationshipSideStatistics, TopNode
from infrahub.graphql.cost.statistics_store import StatisticsStore
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics
from tests.component.graphql.cost.helpers import QUERY_COST_HEADERS
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

PERSONS_CARS_QUERY = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } } } }
            }
        }
    }
}
"""


@dataclass(frozen=True)
class CarOwnership:
    person_ids: dict[str, str]
    """Persons active on main, by name."""

    electric_car_ids: tuple[str, ...]
    gaz_car_ids: tuple[str, ...]


async def _create_person(db: InfrahubDatabase, name: str, branch: Branch | None = None) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name=name)
    await person.save(db=db)
    return person


async def _create_car(db: InfrahubDatabase, kind: str, name: str, owner: Node) -> Node:
    car = await Node.init(db=db, schema=kind)
    if kind == "TestElectricCar":
        await car.new(db=db, name=name, nbr_seats=4, nbr_engine=1, owner=owner)
    else:
        await car.new(db=db, name=name, nbr_seats=5, mpg=40, owner=owner)
    await car.save(db=db)
    return car


@pytest.fixture
async def car_ownership(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics: SchemaRoot
) -> CarOwnership:
    """Persons owning 0, 1, 3 and 10 cars on main, a person deleted on main and a person created on a branch.

    One car of the person with 10 cars first belonged to the deleted person, and on the branch one car of the
    person with 3 cars belongs to the person of the branch.
    """
    cars_by_owner = {
        "Dana": [],
        "Eli": ["TestElectricCar"],
        "Fay": ["TestElectricCar", "TestElectricCar", "TestGazCar"],
        "Gus": ["TestElectricCar"] * 4 + ["TestGazCar"] * 5,
    }
    persons = {name: await _create_person(db=db, name=name) for name in cars_by_owner}
    cars: dict[str, list[Node]] = {"TestElectricCar": [], "TestGazCar": []}
    cars_of_fay: list[Node] = []
    for owner_name, car_kinds in cars_by_owner.items():
        for index, kind in enumerate(car_kinds):
            car = await _create_car(db=db, kind=kind, name=f"{owner_name.lower()}-{index}", owner=persons[owner_name])
            cars[kind].append(car)
            if owner_name == "Fay":
                cars_of_fay.append(car)

    deleted_person = await _create_person(db=db, name="Hal")
    car_of_deleted_person = await _create_car(db=db, kind="TestGazCar", name="hal-0", owner=deleted_person)
    cars["TestGazCar"].append(car_of_deleted_person)
    await car_of_deleted_person.get_relationship(name="owner").update(db=db, data=persons["Gus"])
    await car_of_deleted_person.save(db=db)
    await deleted_person.delete(db=db)

    branch = await create_branch(branch_name="cost-refresh", db=db)
    branch_person = await _create_person(db=db, name="Ivy", branch=branch)
    car_on_branch = await NodeManager.get_one(db=db, branch=branch, id=cars_of_fay[0].id)
    await car_on_branch.get_relationship(name="owner").update(db=db, data=branch_person)
    await car_on_branch.save(db=db)

    return CarOwnership(
        person_ids={name: person.id for name, person in persons.items()},
        electric_car_ids=tuple(car.id for car in cars["TestElectricCar"]),
        gaz_car_ids=tuple(car.id for car in cars["TestGazCar"]),
    )


def _cars_owner_side(car_ids: tuple[str, ...]) -> RelationshipSideStatistics:
    return RelationshipSideStatistics(
        identifier="person__car",
        direction=RelationshipDirection.BIDIR,
        nodes_with_peers=7,
        total_peers=7,
        peers_by_kind={"TestPerson": 7},
        histogram=(HistogramBucket(lower=1, upper=1, node_count=7, max=1),),
        top_nodes=tuple(TopNode(node_id=car_id, peers=1) for car_id in sorted(car_ids)),
    )


async def _read_kinds(cache: MemoryCache, kinds: list[str]) -> dict[str, KindStatistics]:
    store = StatisticsStore(cache=cache)
    pointer = await store.read_pointer()
    assert pointer is not None
    return await store.read_kinds(version=pointer.version, kinds=kinds)


async def test_refresh_stores_the_statistics_of_both_sides_of_a_relationship(
    car_ownership: CarOwnership, memory_cache: MemoryCache
) -> None:
    await refresh_query_cost_statistics()

    statistics = await _read_kinds(cache=memory_cache, kinds=["TestPerson", "TestElectricCar", "TestGazCar"])

    person = statistics["TestPerson"]
    assert person.label_count == 6
    assert person.active_count == 4
    assert person.side(identifier="person__car", direction=RelationshipDirection.BIDIR) == RelationshipSideStatistics(
        identifier="person__car",
        direction=RelationshipDirection.BIDIR,
        nodes_with_peers=3,
        total_peers=14,
        peers_by_kind={"TestElectricCar": 7, "TestGazCar": 7},
        histogram=(
            HistogramBucket(lower=0, upper=0, node_count=1, max=0),
            HistogramBucket(lower=1, upper=1, node_count=1, max=1),
            HistogramBucket(lower=2, upper=3, node_count=1, max=3),
            HistogramBucket(lower=8, upper=15, node_count=1, max=10),
        ),
        top_nodes=(
            TopNode(node_id=car_ownership.person_ids["Gus"], peers=10),
            TopNode(node_id=car_ownership.person_ids["Fay"], peers=3),
            TopNode(node_id=car_ownership.person_ids["Eli"], peers=1),
        ),
    )

    for kind, car_ids in (
        ("TestElectricCar", car_ownership.electric_car_ids),
        ("TestGazCar", car_ownership.gaz_car_ids),
    ):
        cars = statistics[kind]
        assert (cars.label_count, cars.active_count) == (7, 7)
        assert cars.side(identifier="person__car", direction=RelationshipDirection.BIDIR) == _cars_owner_side(
            car_ids=car_ids
        )


async def test_reading_in_chunks_smaller_than_a_kind_gives_the_same_statistics(
    db: InfrahubDatabase, default_branch: Branch, car_ownership: CarOwnership
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    at = Timestamp()
    database = CountingInfrahubDatabase.from_db(db=db)
    in_one_chunk = await StatisticsCollector(
        db=database, branch=default_branch, schema_branch=schema_branch, chunk_size=1000
    ).collect(at=at)
    database.reset_counts()

    in_chunks_of_three = await StatisticsCollector(
        db=database, branch=default_branch, schema_branch=schema_branch, chunk_size=3
    ).collect(at=at)

    assert in_chunks_of_three.kinds == in_one_chunk.kinds
    assert in_chunks_of_three.query_count == database.query_counts.total()
    # Pages of 3 over the 6 persons, deleted and branch persons included, then over the 7 cars of each kind.
    assert database.count_for("graphql-cost-kind-active-node-ids") == 3 + 3 + 3
    sides = {kind.kind: len(kind.relationships) for kind in in_one_chunk.kinds}
    # Chunks of 3 over the ids of the 4 active persons, then over the 7 cars of each kind.
    assert database.count_for("graphql-cost-relationship-side-degree") == (
        2 * sides["TestPerson"] + 3 * sides["TestElectricCar"] + 3 * sides["TestGazCar"]
    )


async def test_refresh_publishes_a_new_version_of_main_at_each_run(
    car_ownership: CarOwnership, memory_cache: MemoryCache
) -> None:
    store = StatisticsStore(cache=memory_cache)

    before_first_run = datetime.now(tz=UTC)
    await refresh_query_cost_statistics()
    after_first_run = datetime.now(tz=UTC)
    first = await store.read_pointer()

    await refresh_query_cost_statistics()
    second = await store.read_pointer()

    assert first is not None
    assert second is not None
    assert (first.version, first.branch) == (1, "main")
    assert before_first_run <= first.computed_at <= after_first_run
    assert (second.version, second.branch) == (2, "main")
    assert {"TestPerson", "TestElectricCar", "TestGazCar"} <= set(second.kinds)
    assert "TestCar" not in second.kinds
    assert sorted(key for key in memory_cache.storage if key != STATISTICS_POINTER_KEY) == sorted(
        f"graphql_cost:statistics:v2:kind:{kind}" for kind in second.kinds
    )


async def test_request_with_cost_details_does_not_compute_statistics(
    car_ownership: CarOwnership, create_test_admin: Node, memory_cache: MemoryCache, counting_client: TestClient
) -> None:
    with counting_client:
        response = counting_client.post("/graphql", json={"query": PERSONS_CARS_QUERY}, headers=QUERY_COST_HEADERS)

    assert response.status_code == 200
    assert response.json()["extensions"]["query_cost"]["statistics"] is None
    assert [key for key in memory_cache.storage if key.startswith("graphql_cost:")] == []

    await refresh_query_cost_statistics()

    pointer = await StatisticsStore(cache=memory_cache).read_pointer()
    assert pointer is not None
    assert pointer.version == 1
