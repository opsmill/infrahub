import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_default_branch, create_global_branch, create_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase

NBR_WARMUP = int(os.getenv("INFRAHUB_BENCHMARK_NBR_WARMUP", "5"))
CAR_COUNT = 600
CARS_OF_JOHN = 3
LOOKED_UP_CAR_INDEX = 300
"""A car owned by the fleet, so a lookup by its name starts from a value that one node holds."""


@dataclass
class FilteredLookupData:
    john_id: str
    fleet_id: str
    car_name: str


@pytest.fixture(scope="module")
async def reset_environment(db: InfrahubDatabase) -> None:
    registry.delete_all()
    await delete_all_nodes(db=db)
    await create_root_node(db=db)


@pytest.fixture(scope="module")
async def default_branch(reset_environment: None, db: InfrahubDatabase) -> Branch:
    branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()
    return branch


@pytest.fixture(scope="module")
async def car_owner_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.load_schema(
        schema=SchemaRoot(
            nodes=[
                {
                    "name": "Person",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [{"name": "name", "kind": "Text"}],
                    "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many"}],
                },
                {
                    "name": "Car",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [{"name": "name", "kind": "Text"}],
                    "relationships": [{"name": "owner", "peer": "TestPerson", "cardinality": "one"}],
                },
            ]
        )
    )
    schema_branch.process()
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    return schema_branch


@pytest.fixture(scope="module")
async def filtered_lookup_data(
    db: InfrahubDatabase, default_branch: Branch, car_owner_schema: SchemaBranch
) -> FilteredLookupData:
    """Two owners and `CAR_COUNT` cars: john owns `CARS_OF_JOHN` of them and the fleet owns every other one."""
    persons: dict[str, Node] = {}
    for name in ("john", "fleet"):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, name=name)
        await person.save(db=db)
        persons[name] = person

    for index in range(CAR_COUNT):
        owner = persons["john"] if index < CARS_OF_JOHN else persons["fleet"]
        car = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car.new(db=db, name=f"car-{index}", owner=owner)
        await car.save(db=db)

    return FilteredLookupData(
        john_id=persons["john"].id, fleet_id=persons["fleet"].id, car_name=f"car-{LOOKED_UP_CAR_INDEX}"
    )


def _run_lookup(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    lookup: Callable[..., Any],
    db: InfrahubDatabase,
    branch: Branch,
    filters: dict[str, Any],
    expected: int,
) -> None:
    """Benchmark `lookup` after a warm-up, which gives Neo4j the time to plan the query text once."""
    result = exec_async(lookup, db=db, schema="TestCar", filters=filters, branch=branch)
    assert (len(result) if isinstance(result, list) else result) == expected

    for _ in range(NBR_WARMUP):
        exec_async(lookup, db=db, schema="TestCar", filters=filters, branch=branch)

    aio_benchmark(lookup, db=db, schema="TestCar", filters=filters, branch=branch)


def test_lookup_by_exact_name(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    filtered_lookup_data: FilteredLookupData,
) -> None:
    """One node holds the value, so the lookup starts from the value."""
    _run_lookup(
        exec_async=exec_async,
        aio_benchmark=aio_benchmark,
        lookup=NodeManager.query,
        db=db,
        branch=default_branch,
        filters={"name__value": filtered_lookup_data.car_name},
        expected=1,
    )


def test_lookup_by_owner_with_few_cars(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    filtered_lookup_data: FilteredLookupData,
) -> None:
    """The owner has few cars, so the lookup starts from the owner."""
    _run_lookup(
        exec_async=exec_async,
        aio_benchmark=aio_benchmark,
        lookup=NodeManager.query,
        db=db,
        branch=default_branch,
        filters={"owner__ids": [filtered_lookup_data.john_id]},
        expected=CARS_OF_JOHN,
    )


def test_count_by_owner_with_most_cars(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    filtered_lookup_data: FilteredLookupData,
) -> None:
    """The owner has most cars, so the count keeps reading every node of the kind and the extra query is a cost."""
    _run_lookup(
        exec_async=exec_async,
        aio_benchmark=aio_benchmark,
        lookup=NodeManager.count,
        db=db,
        branch=default_branch,
        filters={"owner__ids": [filtered_lookup_data.fleet_id]},
        expected=CAR_COUNT - CARS_OF_JOHN,
    )
