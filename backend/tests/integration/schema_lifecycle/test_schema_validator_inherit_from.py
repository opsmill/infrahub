from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete

from ..shared import load_schema
from .shared import (
    TestSchemaLifecycleBase,
)

PERSON_KIND = "TestingPerson"
CYLON_KIND = "TestingCylon"
CAR_KIND = "TestingCar"


class TestSchemaLifecycleValidatorMain(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_car_base(self) -> dict[str, Any]:
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
                    "peer": "TestingHumanoid",
                    "cardinality": "one",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_humanoid_base(self) -> dict[str, Any]:
        return {
            "name": "Humanoid",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Humanoid",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "height", "kind": "Number", "optional": True},
                {"name": "favorite_color", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": "TestingCar", "cardinality": "many"}
            ],
        }

    @pytest.fixture(scope="class")
    def schema_person_base(self) -> dict[str, Any]:
        return {
            "name": "Person",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Person",
            "inherit_from": ["TestingHumanoid"],
            "attributes": [
                {"name": "homeworld", "kind": "Text", "optional": False},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_cylon_base(self) -> dict[str, Any]:
        return {
            "name": "Cylon",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Cylon",
            "inherit_from": ["TestingHumanoid"],
            "attributes": [
                {"name": "model_number", "kind": "Number", "optional": False},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_robot_base(self) -> dict[str, Any]:
        return {
            "name": "Robot",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Robot",
        }

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch_2")

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step_01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        starbuck = await Node.init(schema=PERSON_KIND, db=db)
        await starbuck.new(db=db, name="Kara", height=175, description="Starbuck", homeworld="Caprica")
        await starbuck.save(db=db)

        deleted_person = await Node.init(schema=PERSON_KIND, db=db)
        await deleted_person.new(db=db, name="Deleted", height=175, homeworld="Caprica")
        await deleted_person.save(db=db)
        await deleted_person.delete(db=db)

        gaius = await Node.init(schema=PERSON_KIND, db=db)
        await gaius.new(db=db, name="Gaius", height=155, description="'Scientist'", homeworld="Aerilon")
        await gaius.save(db=db)

        boomer = await Node.init(schema=CYLON_KIND, db=db)
        await boomer.new(db=db, name="Sharon", height=165, model_number=8, description="8 (Boomer)")
        await boomer.save(db=db)

        caprica = await Node.init(schema=CYLON_KIND, db=db)
        await caprica.new(db=db, name="Caprica", height=185, model_number=6, description="6 (Caprica)")
        await caprica.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(db=db, name="Megane", description="Renault Megane", color="#c93420", owner=starbuck)
        await megane.save(db=db)

        objs = {
            "starbuck": starbuck.id,
            "gaius": gaius.id,
            "boomer": boomer.id,
            "caprica": caprica.id,
            "megane": megane.id,
        }

        return objs

    @pytest.fixture(scope="class")
    def schema_01_cylon_robot(self, schema_cylon_base: dict[str, Any]) -> dict[str, Any]:
        schema_cylon_base["inherit_from"] = ["TestingHumanoid", "TestingRobot"]
        return schema_cylon_base

    @pytest.fixture(scope="class")
    def schema_03_cylon_robot(self, schema_cylon_base: dict[str, Any]) -> dict[str, Any]:
        schema_cylon_base["inherit_from"] = []
        return schema_cylon_base

    @pytest.fixture(scope="class")
    def schema_step_01(
        self,
        schema_humanoid_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_cylon_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base],
            "nodes": [schema_car_base, schema_person_base, schema_cylon_base],
        }

    @pytest.fixture(scope="class")
    def schema_step_02_add_generic(
        self,
        schema_humanoid_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_01_cylon_robot: dict[str, Any],
        schema_robot_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base, schema_robot_base],
            "nodes": [schema_car_base, schema_person_base, schema_01_cylon_robot],
        }

    @pytest.fixture(scope="class")
    def schema_step_03_remove_generic(
        self,
        schema_humanoid_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_03_cylon_robot: dict[str, Any],
        schema_robot_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base, schema_robot_base],
            "nodes": [schema_car_base, schema_person_base, schema_03_cylon_robot],
        }

    async def test_baseline_backend(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        cylons = await registry.manager.query(db=db, schema=CYLON_KIND)
        cars = await registry.manager.query(db=db, schema=CAR_KIND)
        assert len(persons) == 2
        assert len(cylons) == 2
        assert len(cars) == 1

    async def test_step_02_add_generic(
        self, client: InfrahubClient, initial_dataset: dict[str, str], schema_step_02_add_generic: dict[str, Any]
    ) -> None:
        success, _ = await client.schema.check(schemas=[schema_step_02_add_generic])
        assert success is True

    async def test_step_03_remove_generic(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        initial_dataset: dict[str, str],
        schema_step_03_remove_generic: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step_03_remove_generic])
        assert success is False
        assert len(response["errors"]) == 1
        error = response["errors"][0]
        assert "Node-level 'inherit_from' constraint violation on schema 'SchemaNode'" in error["message"]
        assert "The error relates to field inherit_from=['TestingHumanoid']." in error["message"]

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
