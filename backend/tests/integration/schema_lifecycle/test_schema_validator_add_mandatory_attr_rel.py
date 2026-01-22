import copy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
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
            "relationships": [],
        }

    @pytest.fixture(scope="class")
    def schema_person_mandatory_attr_no_default(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person = copy.deepcopy(schema_person_base)
        schema_person["attributes"].append({"name": "age", "kind": "Number", "optional": False})
        return schema_person

    @pytest.fixture(scope="class")
    def schema_person_mandatory_rel(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person = copy.deepcopy(schema_person_base)
        schema_person["relationships"].append(
            {"name": "favorite_cars", "peer": CAR_KIND, "optional": False, "cardinality": "many"}
        )
        return schema_person

    @pytest.fixture(scope="class")
    def schema_person_mandatory_attr_default(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person = copy.deepcopy(schema_person_base)
        schema_person["attributes"].append({"name": "age", "kind": "Number", "optional": False, "default_value": 99})
        return schema_person

    @pytest.fixture(scope="class")
    def schema_person_optional_attr(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person = copy.deepcopy(schema_person_base)
        schema_person["attributes"].append({"name": "hair_color", "kind": "Text", "optional": True})
        return schema_person

    @pytest.fixture(scope="class")
    def schema_car_mandatory_attr_no_default(self, schema_car_base: dict[str, Any]) -> dict[str, Any]:
        schema_car = copy.deepcopy(schema_car_base)
        schema_car["attributes"].append({"name": "nbr_wheels", "kind": "Number", "optional": False})
        return schema_car

    @pytest.fixture(scope="class")
    def schema_car_mandatory_attr_default(self, schema_car_base: dict[str, Any]) -> dict[str, Any]:
        schema_car = copy.deepcopy(schema_car_base)
        schema_car["attributes"].append({"name": "nbr_wheels", "kind": "Number", "optional": False, "default_value": 4})
        return schema_car

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

        president = await Node.init(schema=PERSON_KIND, db=db)
        await president.new(db=db, name="Laura", height=175, description="President", homeworld="Caprica")
        await president.save(db=db)

        gaius = await Node.init(schema=PERSON_KIND, db=db)
        await gaius.new(db=db, name="Gaius", height=155, description="'Scientist'", homeworld="Aerilon")
        await gaius.save(db=db)

        boomer = await Node.init(schema=CYLON_KIND, db=db)
        await boomer.new(db=db, name="Sharon", height=165, model_number=8, description="8 (Boomer)")
        await boomer.save(db=db)

        athena = await Node.init(schema=CYLON_KIND, db=db)
        await athena.new(db=db, name="Sharon", height=165, model_number=8, description="8 (Athena)")
        await athena.save(db=db)

        caprica = await Node.init(schema=CYLON_KIND, db=db)
        await caprica.new(db=db, name="Caprica", height=185, model_number=6, description="6 (Caprica)")
        await caprica.save(db=db)

        deleted_cylon = await Node.init(schema=CYLON_KIND, db=db)
        await deleted_cylon.new(db=db, name="<REDACTED>", height=185, model_number=1)
        await deleted_cylon.save(db=db)
        await deleted_cylon.delete(db=db)

        objs = {
            "starbuck": starbuck.id,
            "president": president.id,
            "gaius": gaius.id,
            "boomer": boomer.id,
            "athena": athena.id,
            "caprica": caprica.id,
        }

        return objs

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
    def schema_with_person_mandatory_attr(
        self,
        schema_person_mandatory_attr_no_default: dict[str, Any],
        schema_humanoid_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_cylon_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base],
            "nodes": [schema_person_mandatory_attr_no_default, schema_car_base, schema_cylon_base],
        }

    @pytest.fixture(scope="class")
    def schema_with_person_mandatory_rel(
        self,
        schema_person_mandatory_rel: dict[str, Any],
        schema_humanoid_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_cylon_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base],
            "nodes": [schema_person_mandatory_rel, schema_car_base, schema_cylon_base],
        }

    @pytest.fixture(scope="class")
    def schema_with_person_default_value(
        self,
        schema_person_mandatory_attr_default: dict[str, Any],
        schema_humanoid_base: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base: dict[str, Any],
        schema_cylon_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base],
            "nodes": [schema_person_mandatory_attr_default, schema_car_base, schema_cylon_base],
        }

    @pytest.fixture(scope="class")
    def schema_with_car_mandatory(
        self,
        schema_person_base: dict[str, Any],
        schema_humanoid_base: dict[str, Any],
        schema_car_mandatory_attr_no_default: dict[str, Any],
        schema_cylon_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_humanoid_base],
            "nodes": [schema_person_base, schema_car_mandatory_attr_no_default, schema_cylon_base],
        }

    async def test_baseline_backend(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        cylons = await registry.manager.query(db=db, schema=CYLON_KIND)
        cars = await registry.manager.query(db=db, schema=CAR_KIND)
        assert len(persons) == 3
        assert len(cylons) == 3
        assert len(cars) == 0

    async def test_check_mandatory_attribute_failure(
        self, client: InfrahubClient, initial_dataset: dict[str, str], schema_with_person_mandatory_attr: dict[str, Any]
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_with_person_mandatory_attr])

        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]

        assert "Node-level 'attribute' constraint violation" in err_msg

    async def test_check_mandatory_relationship_failure(
        self, client: InfrahubClient, initial_dataset: dict[str, str], schema_with_person_mandatory_rel: dict[str, Any]
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_with_person_mandatory_rel])

        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]

        assert "Node-level 'relationship' constraint violation" in err_msg

    async def test_check_mandatory_attribute_after_deleting_nodes(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        initial_dataset: dict[str, str],
        schema_with_person_mandatory_attr: dict[str, Any],
    ) -> None:
        """Validate that it's possible to add a new mandatory attribute after deleting all the nodes in scope."""
        branch = await client.branch.create(branch_name="add-attr-delete-nodes")

        for name in ["starbuck", "president", "gaius"]:
            node_id = initial_dataset[name]
            node: Node = await NodeManager.get_one(db=db, id=node_id, branch=branch.name, raise_on_error=True)
            await node.delete(db=db)

        success, response = await client.schema.check(schemas=[schema_with_person_mandatory_attr], branch=branch.name)
        assert success is True

        response = await client.schema.load(schemas=[schema_with_person_mandatory_attr], branch=branch.name)
        assert response.errors == {}

    async def test_check_mandatory_rel_after_deleting_nodes(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        initial_dataset: dict[str, str],
        schema_with_person_mandatory_rel: dict[str, Any],
    ) -> None:
        """Validate that it's possible to add a new mandatory attribute after deleting all the nodes in scope."""
        branch = await client.branch.create(branch_name="add-rel-delete-nodes")

        for name in ["starbuck", "president", "gaius"]:
            node_id = initial_dataset[name]
            node: Node = await NodeManager.get_one(db=db, id=node_id, branch=branch.name, raise_on_error=True)
            await node.delete(db=db)

        success, response = await client.schema.check(schemas=[schema_with_person_mandatory_rel], branch=branch.name)
        assert success is True

        response = await client.schema.load(schemas=[schema_with_person_mandatory_rel], branch=branch.name)
        assert response.errors == {}

    async def test_check_mandatory_attribute_success_no_data(
        self, client: InfrahubClient, initial_dataset: dict[str, str], schema_with_car_mandatory: dict[str, Any]
    ) -> None:
        """Validate that it's possible to add a new mandatory attribute when there is no data in the database."""
        success, _ = await client.schema.check(schemas=[schema_with_car_mandatory])
        assert success is True

    async def test_load_mandatory_attribute_success_no_data(
        self, client: InfrahubClient, initial_dataset: dict[str, str], schema_with_car_mandatory: dict[str, Any]
    ) -> None:
        branch = await client.branch.create(branch_name="add-no-prior-data")
        response = await client.schema.load(schemas=[schema_with_car_mandatory], branch=branch.name)
        assert response.errors == {}

    async def test_check_mandatory_attribute_success_default_value(
        self, client: InfrahubClient, initial_dataset: dict[str, str], schema_with_person_default_value: dict[str, Any]
    ) -> None:
        """Validate that it's possible to add a new mandatory attribute with a default value."""
        success, _ = await client.schema.check(schemas=[schema_with_person_default_value])
        assert success is True

    async def test_load_mandatory_attribute_success_default_value(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_with_person_default_value: dict[str, Any],
    ) -> None:
        branch = await client.branch.create(branch_name="add-default-value")
        response = await client.schema.load(schemas=[schema_with_person_default_value], branch=branch.name)
        assert response.errors == {}

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
