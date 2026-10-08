from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase, get_db
from infrahub.graphql.cost.request_estimate import get_statistics_snapshot_holder
from infrahub.workers.dependencies import build_database
from tests.component.graphql.cost.helpers import CARS_BY_PERSON
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from collections.abc import Generator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch


@pytest.fixture(autouse=True)
def fresh_statistics_snapshot_holder() -> Generator[None, None, None]:
    """Leave out of each test the statistics that another test loaded into the process."""
    get_statistics_snapshot_holder.cache_clear()
    yield
    get_statistics_snapshot_holder.cache_clear()


@pytest.fixture
def counting_database_class() -> type[CountingInfrahubDatabase]:
    return CountingInfrahubDatabase


@pytest.fixture
def counting_client(
    counting_database_class: type[CountingInfrahubDatabase],
    dependency_provider: Provider,
    nats: dict[int, int] | None,
    redis: dict[int, int] | None,
) -> Generator[TestClient, None, None]:
    """Client of an application whose database counts the queries and rows of every session."""
    # Importing the application loads every module it serves, so it waits until the client is needed.
    from infrahub.server import app  # noqa: PLC0415

    async def _counting_db(singleton: bool = True) -> InfrahubDatabase:
        return counting_database_class(driver=await get_db(retry=5))

    with override_dependency(build_database, _counting_db, dependency_provider=dependency_provider):
        yield TestClient(app)


@pytest.fixture
async def car_fleet(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    create_test_admin: Node,
) -> dict[str, Node]:
    """Persons owning 0, 2 and 5 cars."""
    persons: dict[str, Node] = {}
    for person_name, car_count in CARS_BY_PERSON.items():
        person = await Node.init(db=db, schema="TestPerson")
        await person.new(db=db, name=person_name, height=170)
        await person.save(db=db)
        persons[person_name] = person
        for index in range(car_count):
            car = await Node.init(db=db, schema="TestCar")
            await car.new(db=db, name=f"{person_name.lower()}-{index}", nbr_seats=4, owner=person)
            await car.save(db=db)
    return persons
