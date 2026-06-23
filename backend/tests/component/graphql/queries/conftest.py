from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def two_cars_one_owner(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> tuple[Node, Node, Node]:
    return await do_two_cars_one_owner(db=db, branch=default_branch)


@pytest.fixture(scope="class")
async def two_cars_one_owner_scope_class(
    db: InfrahubDatabase, default_branch_scope_class: Branch, car_person_schema_scope_class: SchemaBranch
) -> tuple[Node, Node, Node]:
    return await do_two_cars_one_owner(db=db, branch=default_branch_scope_class)


async def do_two_cars_one_owner(db: InfrahubDatabase, branch: Branch) -> tuple[Node, Node, Node]:
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Alice", height=170)
    await person.save(db=db)

    car_a = await Node.init(db=db, schema="TestCar", branch=branch)
    await car_a.new(db=db, name="Roadster", is_electric=True, nbr_seats=2, color="#ff0000", owner=person)
    await car_a.save(db=db)

    car_b = await Node.init(db=db, schema="TestCar", branch=branch)
    await car_b.new(db=db, name="Sedan", is_electric=False, nbr_seats=4, color="#0000ff", owner=person)
    await car_b.save(db=db)

    return car_a, car_b, person
