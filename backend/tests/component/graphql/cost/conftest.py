from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node
from tests.component.graphql.cost.helpers import CARS_BY_PERSON

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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
