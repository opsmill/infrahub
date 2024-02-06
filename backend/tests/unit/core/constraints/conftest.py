from typing import Dict

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def car_person_schema_generics_simple(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    SCHEMA = {
        "generics": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "order_by": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "identifier": "person__car",
                        "optional": False,
                        "cardinality": "one",
                    },
                    {
                        "name": "previous_owner",
                        "peer": "TestPerson",
                        "identifier": "person_previous__car",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "ElectricCar",
                "namespace": "Test",
                "display_labels": ["name__value", "color__value"],
                "inherit_from": ["TestCar"],
                "default_filter": "name__value",
                "attributes": [
                    {"name": "nbr_engine", "kind": "Number"},
                ],
            },
            {
                "name": "GazCar",
                "namespace": "Test",
                "display_labels": ["name__value", "color__value"],
                "inherit_from": ["TestCar"],
                "default_filter": "name__value",
                "attributes": [
                    {"name": "mpg", "kind": "Number"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {"name": "cars", "peer": "TestCar", "identifier": "person__car", "cardinality": "many"}
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def car_person_generics_data_simple(db: InfrahubDatabase, car_person_schema_generics_simple) -> Dict[str, Node]:
    ecar = registry.schema.get(name="TestElectricCar")
    gcar = registry.schema.get(name="TestGazCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=ecar)
    await c1.new(db=db, name="volt", nbr_seats=4, nbr_engine=4, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=ecar)
    await c2.new(db=db, name="bolt", nbr_seats=4, nbr_engine=2, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=gcar)
    await c3.new(db=db, name="nolt", nbr_seats=4, mpg=25, owner=p2)
    await c3.save(db=db)

    nodes = {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
    }

    return nodes
