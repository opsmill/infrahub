from typing import Any, Dict

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from ..shared import load_schema
from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    PERSON_KIND,
    TAG_KIND,
    TestSchemaLifecycleBase,
)

# pylint: disable=unused-argument
ACCORD_COLOR = "#3443eb"


class TestSchemaLifecycleValidatorMain(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry, schema_step01):
        await load_schema(db=db, schema=schema_step01)

        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

        jane = await Node.init(schema=PERSON_KIND, db=db)
        await jane.new(db=db, name="Jane", height=165, description="The famous Jane Doe")
        await jane.save(db=db)

        honda = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await honda.new(db=db, name="honda", description="Honda Motor Co., Ltd")
        await honda.save(db=db)

        renault = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await renault.new(
            db=db, name="renault", description="Groupe Renault is a French multinational automobile manufacturer"
        )
        await renault.save(db=db)

        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(
            db=db, name="accord", description="Honda Accord", color=ACCORD_COLOR, manufacturer=honda, owner=jane
        )
        await accord.save(db=db)

        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(db=db, name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=jane)
        await civic.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(
            db=db, name="Megane", description="Renault Megane", color="#c93420", manufacturer=renault, owner=john
        )
        await megane.save(db=db)

        blue = await Node.init(schema=TAG_KIND, db=db)
        await blue.new(db=db, name="blue", cars=[accord, civic], persons=[jane])
        await blue.save(db=db)

        red = await Node.init(schema=TAG_KIND, db=db)
        await red.new(db=db, name="red", persons=[john])
        await red.save(db=db)

        objs = {
            "john": john.id,
            "jane": jane.id,
            "honda": honda.id,
            "renault": renault.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
            "blue": blue.id,
            "red": red.id,
        }

        return objs

    @pytest.fixture(scope="class")
    def schema_01_person_name_regex_failure(self, schema_person_base) -> Dict[str, Any]:
        """Add regex to TestPerson.name that does not fit existing data"""
        schema_person_base["attributes"][0]["regex"] = "^Q[0-9]+$"
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_01_attr_regex_failure(
        self, schema_car_base, schema_01_person_name_regex_failure, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_01_person_name_regex_failure, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_02_person_name_regex_success(self, schema_person_base) -> Dict[str, Any]:
        """Add regex to TestPerson.name that fits existing data"""
        schema_person_base["attributes"][0]["regex"] = "^J[a-z]+$"
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_02_attr_regex(
        self, schema_car_base, schema_02_person_name_regex_success, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_02_person_name_regex_success, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_03_tag_car_cardinality_failure(self, schema_tag_base) -> Dict[str, Any]:
        """Update TestingTag.cars.cardinality to one, invalid"""
        schema_tag_base["relationships"][0]["cardinality"] = "one"
        return schema_tag_base

    @pytest.fixture(scope="class")
    def schema_03_relationship_cardinality_failure(
        self, schema_car_base, schema_person_base, schema_manufacturer_base, schema_03_tag_car_cardinality_failure
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_base,
                schema_car_base,
                schema_manufacturer_base,
                schema_03_tag_car_cardinality_failure,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_04_tag_person_cardinality_success(self, schema_tag_base) -> Dict[str, Any]:
        """Update TestingTag.persons.cardinality to one, fits existing data"""
        schema_tag_base["relationships"][0]["cardinality"] = "many"
        schema_tag_base["relationships"][1]["cardinality"] = "one"
        return schema_tag_base

    @pytest.fixture(scope="class")
    def schema_04_relationship_cardinality(
        self, schema_car_base, schema_person_base, schema_manufacturer_base, schema_04_tag_person_cardinality_success
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_base,
                schema_car_base,
                schema_manufacturer_base,
                schema_04_tag_person_cardinality_success,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_05_car_color_unique(self, schema_car_base) -> Dict[str, Any]:
        """Update TestingCar.color to unique, invalid"""
        schema_car_base["attributes"][2]["unique"] = "true"
        return schema_car_base

    @pytest.fixture(scope="class")
    def schema_05_attribute_unique(
        self, schema_05_car_color_unique, schema_person_base, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_base,
                schema_05_car_color_unique,
                schema_manufacturer_base,
                schema_tag_base,
            ],
        }

    async def test_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        cars = await registry.manager.query(db=db, schema=CAR_KIND)
        tags = await registry.manager.query(db=db, schema=TAG_KIND)
        assert len(persons) == 2
        assert len(cars) == 3
        assert len(tags) == 2

    async def test_step_01_check_attr_regex_add_failure(
        self, client: InfrahubClient, initial_dataset, schema_01_attr_regex_failure
    ):
        success, response = await client.schema.check(schemas=[schema_01_attr_regex_failure])

        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]
        assert initial_dataset["john"] in err_msg
        assert initial_dataset["jane"] in err_msg
        assert "attribute.regex.update" in err_msg

    async def test_step_02_check_attr_regex_add_success(
        self, client: InfrahubClient, initial_dataset, schema_02_attr_regex
    ):
        success, response = await client.schema.check(schemas=[schema_02_attr_regex])
        assert success
        assert response == {
            "diff": {
                "added": {},
                "removed": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "removed": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "removed": {},
                                "changed": {
                                    "name": {
                                        "added": {},
                                        "changed": {"regex": None},
                                        "removed": {},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

    async def test_step_03_check_relationship_cardinality_change_failure(
        self, client: InfrahubClient, initial_dataset, schema_03_relationship_cardinality_failure
    ):
        success, response = await client.schema.check(schemas=[schema_03_relationship_cardinality_failure])
        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]
        assert initial_dataset["blue"] in err_msg
        assert "relationship.count.update" in err_msg

    async def test_step_04_check_relationship_cardinality_change_success(
        self, client: InfrahubClient, initial_dataset, schema_04_relationship_cardinality
    ):
        success, response = await client.schema.check(schemas=[schema_04_relationship_cardinality])

        assert success
        assert "diff" in response
        assert "changed" in response["diff"]
        assert "TestingTag" in response["diff"]["changed"]
        assert response["diff"]["changed"]["TestingTag"] == {
            "added": {},
            "removed": {},
            "changed": {
                "relationships": {
                    "added": {},
                    "removed": {},
                    "changed": {
                        "persons": {
                            "added": {},
                            "changed": {
                                "cardinality": None,
                                "max_count": None,
                            },
                            "removed": {},
                        },
                    },
                },
            },
        }

    async def test_step_05_check_attribute_unique_change_failure(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_05_attribute_unique
    ):
        pinto = await Node.init(schema=CAR_KIND, db=db)
        await pinto.new(
            db=db,
            name="pinto",
            description="Honda Pinto",
            color=ACCORD_COLOR,
            manufacturer=initial_dataset["honda"],
            owner=initial_dataset["jane"],
        )
        await pinto.save(db=db)

        success, response = await client.schema.check(schemas=[schema_05_attribute_unique])
        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]
        assert pinto.id in err_msg
        assert initial_dataset["accord"] in err_msg
        assert "attribute.unique.update" in err_msg

    async def test_step_06_check_attribute_unique_change_success(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_05_attribute_unique
    ):
        pinto = await NodeManager.get_one_by_default_filter(db=db, id="pinto", schema_name="TestingCar")
        await pinto.delete(db=db)

        success, response = await client.schema.check(schemas=[schema_05_attribute_unique])

        assert success
        assert "diff" in response
        assert "changed" in response["diff"]
        assert "TestingCar" in response["diff"]["changed"]
        assert response["diff"]["changed"]["TestingCar"] == {
            "added": {},
            "removed": {},
            "changed": {
                "attributes": {
                    "added": {},
                    "removed": {},
                    "changed": {
                        "color": {
                            "added": {},
                            "changed": {
                                "unique": None,
                            },
                            "removed": {},
                        },
                    },
                },
            },
        }
