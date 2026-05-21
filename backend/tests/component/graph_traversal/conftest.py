from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def jack_with_blue_tag(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> tuple[Node, Node]:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, firstname="Jack", lastname="Russell", primary_tag=tag_blue_main)
    await person.save(db=db)
    return person, tag_blue_main


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
