from typing import Any, Dict

import pytest

from tests.helpers.test_app import TestInfrahubApp

PERSON_KIND = "TestingPerson"
CAR_KIND = "TestingCar"
MANUFACTURER_KIND_01 = "TestingManufacturer"
MANUFACTURER_KIND_03 = "TestingCarMaker"
TAG_KIND = "TestingTag"


class TestSchemaLifecycleBase(TestInfrahubApp):
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
    def schema_person_02_first_last(self, schema_person_base) -> Dict[str, Any]:
        """Rename the attribute name to firstname and add a new lastname attribute."""
        assert schema_person_base["attributes"][0]["name"] == "name"
        schema_person_base["attributes"][0]["name"] = "firstname"
        schema_person_base["attributes"].append({"name": "lastname", "kind": "Text"})
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_person_03_no_height(self, schema_person_02_first_last) -> Dict[str, Any]:
        """Remove the attribute height."""
        person = schema_person_02_first_last
        assert person["attributes"][2]["name"] == "height"
        person["attributes"][2]["state"] = "absent"
        return person

    @pytest.fixture(scope="class")
    def schema_car_base(self) -> Dict[str, Any]:
        return {
            "name": "Car",
            "namespace": "Testing",
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
    def schema_car_02_carmaker(self, schema_car_base, schema_manufacturer_02_car_maker) -> Dict[str, Any]:
        manufacturer = schema_manufacturer_02_car_maker
        schema_car_base["relationships"][1]["peer"] = f"{manufacturer['namespace']}{manufacturer['name']}"
        return schema_car_base

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
    def schema_manufacturer_02_car_maker(self, schema_manufacturer_base) -> Dict[str, Any]:
        schema_manufacturer_base["name"] = "CarMaker"
        schema_manufacturer_base["label"] = "CarMaker"
        return schema_manufacturer_base

    @pytest.fixture(scope="class")
    def schema_tag_base(self) -> Dict[str, Any]:
        return {
            "name": "Tag",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Testing Tag",
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": "TestingCar", "cardinality": "many"},
                {
                    "name": "persons",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingPerson",
                    "cardinality": "many",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_tag_04_absent(self, schema_tag_base) -> Dict[str, Any]:
        schema_tag_base["state"] = "absent"
        return schema_tag_base

    @pytest.fixture(scope="class")
    def schema_step01(
        self, schema_car_base, schema_person_base, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_step02(
        self, schema_car_base, schema_person_02_first_last, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_02_first_last, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_step03(
        self, schema_car_02_carmaker, schema_person_03_no_height, schema_manufacturer_02_car_maker, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_03_no_height,
                schema_car_02_carmaker,
                schema_manufacturer_02_car_maker,
                schema_tag_base,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step04(
        self, schema_car_02_carmaker, schema_person_03_no_height, schema_manufacturer_02_car_maker, schema_tag_04_absent
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_03_no_height,
                schema_car_02_carmaker,
                schema_manufacturer_02_car_maker,
                schema_tag_04_absent,
            ],
        }
