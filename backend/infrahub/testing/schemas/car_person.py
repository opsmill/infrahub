from typing import Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.node import InfrahubNode

NAMESPACE = "Testing"

TESTING_MANUFACTURER = f"{NAMESPACE}Manufacturer"
TESTING_PERSON = f"{NAMESPACE}Person"
TESTING_CAR = f"{NAMESPACE}Car"


class SchemaCarPerson:
    @pytest.fixture(scope="class")
    def schema_person_base(self) -> dict[str, Any]:
        return {
            "name": "Person",
            "namespace": NAMESPACE,
            "include_in_menu": True,
            "label": "Person",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "height", "kind": "Number", "optional": True},
            ],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": TESTING_CAR, "cardinality": "many"}
            ],
        }

    @pytest.fixture(scope="class")
    def schema_car_base(self) -> dict[str, Any]:
        return {
            "name": "Car",
            "namespace": NAMESPACE,
            "include_in_menu": True,
            "default_filter": "name__value",
            "label": "Car",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "color", "kind": "Text"},
            ],
            "relationships": [
                {
                    "name": "owner",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": TESTING_PERSON,
                    "cardinality": "one",
                },
                {
                    "name": "manufacturer",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": TESTING_MANUFACTURER,
                    "cardinality": "one",
                    "identifier": "car__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_manufacturer_base(self) -> dict[str, Any]:
        return {
            "name": "Manufacturer",
            "namespace": NAMESPACE,
            "include_in_menu": True,
            "label": "Manufacturer",
            "attributes": [{"name": "name", "kind": "Text"}, {"name": "description", "kind": "Text", "optional": True}],
            "relationships": [
                {
                    "name": "cars",
                    "kind": "Generic",
                    "optional": True,
                    "peer": TESTING_CAR,
                    "cardinality": "many",
                    "identifier": "car__manufacturer",
                },
                {
                    "name": "customers",
                    "kind": "Generic",
                    "optional": True,
                    "peer": TESTING_PERSON,
                    "cardinality": "many",
                    "identifier": "person__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_base(
        self,
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_car_base, schema_manufacturer_base],
        }

    @classmethod
    async def create_persons(cls, client: InfrahubClient, branch: str) -> list[InfrahubNode]:
        john = await client.create(kind=TESTING_PERSON, name="John Doe", branch=branch)
        await john.save()

        jane = await client.create(kind=TESTING_PERSON, name="Jane Doe", branch=branch)
        await jane.save()

        return [john, jane]

    @classmethod
    async def create_manufacturers(cls, client: InfrahubClient, branch: str) -> list[InfrahubNode]:
        obj1 = await client.create(kind=TESTING_MANUFACTURER, name="Volkswagen", branch=branch)
        await obj1.save()

        obj2 = await client.create(kind=TESTING_MANUFACTURER, name="Renault", branch=branch)
        await obj2.save()

        obj3 = await client.create(kind=TESTING_MANUFACTURER, name="Mercedes", branch=branch)
        await obj3.save()

        return [obj1, obj2, obj3]
