from typing import Any, Dict

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

# pylint: disable=unused-argument
ACCORD_COLOR = "#3443eb"
PERSON_KIND = "TestingPerson"
CAR_KIND = "TestingCar"
MANUFACTURER_KIND = "TestingManufacturer"


class TestSDKNodeCreateConstraints(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_person_base(self) -> Dict[str, Any]:
        return {
            "name": "Person",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Person",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "height", "kind": "Number", "optional": True},
            ],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": "TestingCar", "cardinality": "many"}
            ],
        }

    @pytest.fixture(scope="class")
    def schema_manufacturer_base(self) -> Dict[str, Any]:
        return {
            "name": "Manufacturer",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Manufacturer",
            "attributes": [{"name": "name", "kind": "Text"}, {"name": "description", "kind": "Text", "optional": True}],
            "relationships": [
                {
                    "name": "cars",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingCar",
                    "cardinality": "many",
                    "identifier": "car__manufacturer",
                },
                {
                    "name": "customers",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingPerson",
                    "cardinality": "many",
                    "identifier": "person__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_car_base(self) -> Dict[str, Any]:
        return {
            "name": "Car",
            "namespace": "Testing",
            "include_in_menu": True,
            "default_filter": "name__value",
            "label": "Car",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "color", "kind": "Text"},
                {"name": "nbr_seats", "kind": "Number"},
            ],
            "relationships": [
                {
                    "name": "owner",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": "TestingPerson",
                    "cardinality": "one",
                },
                {
                    "name": "manufacturer",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": "TestingManufacturer",
                    "cardinality": "one",
                    "identifier": "car__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step01(self, schema_car_base, schema_person_base, schema_manufacturer_base) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_car_base, schema_manufacturer_base],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry, schema_step01):
        await load_schema(db=db, schema=schema_step01)

        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

        jane = await Node.init(schema=PERSON_KIND, db=db)
        await jane.new(db=db, name="Jane", height=165, description="The famous Jane Doe")
        await jane.save(db=db)

        honda = await Node.init(schema=MANUFACTURER_KIND, db=db)
        await honda.new(db=db, name="honda", description="Honda Motor Co., Ltd")
        await honda.save(db=db)

        renault = await Node.init(schema=MANUFACTURER_KIND, db=db)
        await renault.new(
            db=db, name="renault", description="Groupe Renault is a French multinational automobile manufacturer"
        )
        await renault.save(db=db)

        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(
            db=db,
            name="accord",
            description="Honda Accord",
            color=ACCORD_COLOR,
            manufacturer=honda,
            owner=jane,
            nbr_seats=5,
        )
        await accord.save(db=db)

        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(
            db=db, name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=jane, nbr_seats=4
        )
        await civic.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(
            db=db,
            name="Megane",
            description="Renault Megane",
            color="#c93420",
            manufacturer=renault,
            owner=john,
            nbr_seats=3,
        )
        await megane.save(db=db)

        objs = {
            "john": john.id,
            "jane": jane.id,
            "honda": honda.id,
            "renault": renault.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
        }

        return objs

    @pytest.fixture(scope="class")
    def schema_02_car_uniqueness_constraint(self, schema_car_base) -> Dict[str, Any]:
        schema_car_base["uniqueness_constraints"] = [["owner", "color"]]
        return schema_car_base

    @pytest.fixture(scope="class")
    def schema_02_uniqueness_constraint(
        self, schema_person_base, schema_02_car_uniqueness_constraint, schema_manufacturer_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_02_car_uniqueness_constraint, schema_manufacturer_base],
        }

    @pytest.fixture(scope="class")
    def schema_03_car_uniqueness_constraint(self, schema_car_base) -> Dict[str, Any]:
        schema_car_base["uniqueness_constraints"] = [["owner", "nbr_seats"]]
        return schema_car_base

    @pytest.fixture(scope="class")
    def schema_03_uniqueness_constraint(
        self, schema_person_base, schema_03_car_uniqueness_constraint, schema_manufacturer_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_03_car_uniqueness_constraint, schema_manufacturer_base],
        }

    async def test_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        cars = await registry.manager.query(db=db, schema=CAR_KIND)
        assert len(persons) == 2
        assert len(cars) == 3

    async def test_step_02_add_node_success(
        self, client: InfrahubClient, initial_dataset, schema_02_uniqueness_constraint
    ):
        response = await client.schema.load(schemas=[schema_02_uniqueness_constraint])
        assert not response.errors

        john_person = await client.get(kind=PERSON_KIND, id=initial_dataset["john"])
        honda_manufacturer = await client.get(kind=MANUFACTURER_KIND, id=initial_dataset["honda"])
        new_car = await client.create(
            kind=CAR_KIND,
            name="New",
            owner=john_person,
            manufacturer=honda_manufacturer,
            color=ACCORD_COLOR,
            nbr_seats=2,
        )
        await new_car.save()

        retrieved_car = await client.get(kind=CAR_KIND, id=new_car.id)
        assert retrieved_car.name.value == "New"
        assert retrieved_car.owner.id == initial_dataset["john"]
        assert retrieved_car.manufacturer.id == initial_dataset["honda"]

    async def test_step_02_add_node_failure(
        self, client: InfrahubClient, initial_dataset, schema_02_uniqueness_constraint
    ):
        john_person = await client.get(kind=PERSON_KIND, id=initial_dataset["john"])
        renault_manufacturer = await client.get(kind=MANUFACTURER_KIND, id=initial_dataset["renault"])
        new_car = await client.create(
            kind=CAR_KIND,
            name="New2",
            owner=john_person,
            manufacturer=renault_manufacturer,
            color=ACCORD_COLOR,
            nbr_seats=3,
        )

        with pytest.raises(GraphQLError) as exc:
            await new_car.save()

        assert "owner-color" in exc.value.message

    async def test_step_03_add_node_success(
        self, client: InfrahubClient, initial_dataset, schema_03_uniqueness_constraint
    ):
        response = await client.schema.load(schemas=[schema_03_uniqueness_constraint])
        assert not response.errors

        john_person = await client.get(kind=PERSON_KIND, id=initial_dataset["john"])
        honda_manufacturer = await client.get(kind=MANUFACTURER_KIND, id=initial_dataset["honda"])
        new_car = await client.create(
            kind=CAR_KIND,
            name="OneSeater",
            owner=john_person,
            manufacturer=honda_manufacturer,
            color="#112233",
            nbr_seats=1,
        )

        await new_car.save()

        retrieved_car = await client.get(kind=CAR_KIND, id=new_car.id)
        assert retrieved_car.name.value == "OneSeater"
        assert retrieved_car.nbr_seats.value == 1
        assert retrieved_car.owner.id == initial_dataset["john"]
        assert retrieved_car.manufacturer.id == initial_dataset["honda"]

    async def test_step_03_add_node_failure(
        self, client: InfrahubClient, initial_dataset, schema_03_uniqueness_constraint
    ):
        john_person = await client.get(kind=PERSON_KIND, id=initial_dataset["john"])
        renault_manufacturer = await client.get(kind=MANUFACTURER_KIND, id=initial_dataset["renault"])
        new_car = await client.create(
            kind=CAR_KIND,
            name="AnotherOneSeater",
            owner=john_person,
            manufacturer=renault_manufacturer,
            color="#223344",
            nbr_seats=1,
        )

        with pytest.raises(GraphQLError) as exc:
            await new_car.save()

        assert "owner-nbr_seats" in exc.value.message
