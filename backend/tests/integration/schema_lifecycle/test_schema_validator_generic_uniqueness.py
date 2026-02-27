from typing import Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

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
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch_2")

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step_01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        starbuck = await Node.init(schema=PERSON_KIND, db=db)
        await starbuck.new(
            db=db, name="Kara", height=175, description="Starbuck", homeworld="Caprica", favorite_color="army green"
        )
        await starbuck.save(db=db)

        president = await Node.init(schema=PERSON_KIND, db=db)
        await president.new(db=db, name="Laura", height=175, description="President", homeworld="Caprica")
        await president.save(db=db)

        deleted_person = await Node.init(schema=PERSON_KIND, db=db)
        await deleted_person.new(db=db, name="Deleted", height=175, homeworld="Caprica")
        await deleted_person.save(db=db)
        await deleted_person.delete(db=db)

        gaius = await Node.init(schema=PERSON_KIND, db=db)
        await gaius.new(
            db=db, name="Gaius", height=155, description="'Scientist'", homeworld="Aerilon", favorite_color="Gaius"
        )
        await gaius.save(db=db)

        boomer = await Node.init(schema=CYLON_KIND, db=db)
        await boomer.new(
            db=db, name="Sharon", height=165, model_number=8, description="8 (Boomer)", favorite_color="Cylon silver"
        )
        await boomer.save(db=db)

        athena = await Node.init(schema=CYLON_KIND, db=db)
        await athena.new(
            db=db, name="Sharon", height=165, model_number=8, description="8 (Athena)", favorite_color="Cylon chrome"
        )
        await athena.save(db=db)

        caprica = await Node.init(schema=CYLON_KIND, db=db)
        await caprica.new(db=db, name="Caprica", height=185, model_number=6, description="6 (Caprica)")
        await caprica.save(db=db)

        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(db=db, name="accord", description="Honda Accord", color="#12345e", owner=president)
        await accord.save(db=db)

        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(db=db, name="civic", description="Honda Civic", color="#c9eb34", owner=boomer)
        await civic.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(db=db, name="Megane", description="Renault Megane", color="#c93420", owner=starbuck)
        await megane.save(db=db)

        objs = {
            "starbuck": starbuck.id,
            "president": president.id,
            "gaius": gaius.id,
            "boomer": boomer.id,
            "athena": athena.id,
            "caprica": caprica.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
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
    def schema_01_humanoid_uniqueness_constraint_failure(self, schema_humanoid_base: dict[str, Any]) -> dict[str, Any]:
        """Add uniqueness constraint to TestHumanoid that does not fit existing data"""
        schema_humanoid_base["uniqueness_constraints"] = [["height__value", "name__value"]]
        return schema_humanoid_base

    @pytest.fixture(scope="class")
    def schema_01_generic_uniqueness_failure(
        self,
        schema_01_humanoid_uniqueness_constraint_failure: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_cylon_base: dict[str, Any],
        schema_person_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_01_humanoid_uniqueness_constraint_failure],
            "nodes": [schema_car_base, schema_person_base, schema_cylon_base],
        }

    @pytest.fixture(scope="class")
    def schema_02_humanoid_uniqueness_constraint_failure(self, schema_humanoid_base: dict[str, Any]) -> dict[str, Any]:
        schema_humanoid_base["uniqueness_constraints"] = [["name__value", "favorite_color__value"]]
        return schema_humanoid_base

    @pytest.fixture(scope="class")
    def schema_02_generic_uniqueness_failure(
        self,
        schema_02_humanoid_uniqueness_constraint_failure: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_cylon_base: dict[str, Any],
        schema_person_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_02_humanoid_uniqueness_constraint_failure],
            "nodes": [schema_car_base, schema_person_base, schema_cylon_base],
        }

    @pytest.fixture(scope="class")
    def schema_03_humanoid_uniqueness_constraint_failure(self, schema_humanoid_base: dict[str, Any]) -> dict[str, Any]:
        schema_humanoid_base["uniqueness_constraints"] = [["height__value", "name__value"]]
        return schema_humanoid_base

    @pytest.fixture(scope="class")
    def schema_03_person_constraint_failure(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person_base["uniqueness_constraints"] = [["height__value", "homeworld__value"]]
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_03_cylon_constraint_failure(self, schema_cylon_base: dict[str, Any]) -> dict[str, Any]:
        schema_cylon_base["uniqueness_constraints"] = [["model_number__value", "favorite_color__value"]]
        return schema_cylon_base

    @pytest.fixture(scope="class")
    def schema_03_generic_and_node_uniqueness_failure(
        self,
        schema_03_humanoid_uniqueness_constraint_failure: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_03_cylon_constraint_failure: dict[str, Any],
        schema_03_person_constraint_failure: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_03_humanoid_uniqueness_constraint_failure],
            "nodes": [schema_car_base, schema_03_person_constraint_failure, schema_03_cylon_constraint_failure],
        }

    @pytest.fixture(scope="class")
    def schema_04_humanoid_uniqueness_constraint_failure(self, schema_humanoid_base: dict[str, Any]) -> dict[str, Any]:
        schema_humanoid_base["uniqueness_constraints"] = [["name__value", "favorite_color__value"]]
        return schema_humanoid_base

    @pytest.fixture(scope="class")
    def schema_04_person_constraint_failure(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person_base["uniqueness_constraints"] = [["homeworld__value", "favorite_color__value"]]
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_04_cylon_constraint_failure(self, schema_cylon_base: dict[str, Any]) -> dict[str, Any]:
        schema_cylon_base["uniqueness_constraints"] = [["model_number__value", "favorite_color__value"]]
        return schema_cylon_base

    @pytest.fixture(scope="class")
    def schema_04_generic_and_node_uniqueness_failure(
        self,
        schema_04_humanoid_uniqueness_constraint_failure: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_04_cylon_constraint_failure: dict[str, Any],
        schema_04_person_constraint_failure: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_04_humanoid_uniqueness_constraint_failure],
            "nodes": [schema_car_base, schema_04_person_constraint_failure, schema_04_cylon_constraint_failure],
        }

    async def test_baseline_backend(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        cylons = await registry.manager.query(db=db, schema=CYLON_KIND)
        cars = await registry.manager.query(db=db, schema=CAR_KIND)
        assert len(persons) == 3
        assert len(cylons) == 3
        assert len(cars) == 3

    async def test_step_01_check_generic_uniqueness_constraint_failure(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_01_generic_uniqueness_failure: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_01_generic_uniqueness_failure])

        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]
        assert initial_dataset["boomer"] in err_msg
        assert initial_dataset["athena"] in err_msg
        assert "Node-level 'uniqueness_constraints'" in err_msg

    async def test_step_02_check_generic_uniqueness_constraint_rebase_failure(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        initial_dataset: dict[str, str],
        schema_02_generic_uniqueness_failure: dict[str, Any],
        branch_2: Branch,
    ) -> None:
        response = await client.schema.load(schemas=[schema_02_generic_uniqueness_failure], branch=branch_2.name)
        assert not response.errors

        boomer_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["boomer"]
        )
        boomer_main.favorite_color.value = "green"  # type: ignore[attr-defined]
        await boomer_main.save(db=db)
        athena_branch = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["athena"], branch=branch_2
        )
        athena_branch.favorite_color.value = "green"  # type: ignore[attr-defined]
        await athena_branch.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.branch.rebase(branch_name=branch_2.name)

        assert initial_dataset["boomer"] in exc.value.message
        assert initial_dataset["athena"] in exc.value.message
        assert "Node-level 'uniqueness_constraints'" in exc.value.message

    async def test_step_03_check_generic_and_node_uniqueness_constraint_failure(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_03_generic_and_node_uniqueness_failure: dict[str, Any],
    ) -> None:
        boomer_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["boomer"]
        )
        boomer_main.favorite_color.value = "green"  # type: ignore[attr-defined]
        await boomer_main.save(db=db)
        caprica_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["caprica"]
        )
        caprica_main.favorite_color.value = "green"  # type: ignore[attr-defined]
        await caprica_main.save(db=db)

        success, response = await client.schema.check(schemas=[schema_03_generic_and_node_uniqueness_failure])

        assert success is False
        assert "errors" in response
        assert len(response["errors"]) == 1
        err_msg = response["errors"][0]["message"]
        assert initial_dataset["boomer"] in err_msg
        assert initial_dataset["athena"] in err_msg
        assert initial_dataset["starbuck"] in err_msg
        assert initial_dataset["president"] in err_msg
        assert initial_dataset["gaius"] not in err_msg
        assert "Node-level 'uniqueness_constraints'" in err_msg

    async def test_step_03_reset(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        boomer_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["boomer"]
        )
        boomer_main.favorite_color.value = None  # type: ignore[attr-defined]
        await boomer_main.save(db=db)
        caprica_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["caprica"]
        )
        caprica_main.favorite_color.value = None  # type: ignore[attr-defined]
        await caprica_main.save(db=db)

    async def test_step_04_check_generic_and_node_uniqueness_constraint_rebase_failure(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        initial_dataset: dict[str, str],
        schema_04_generic_and_node_uniqueness_failure: dict[str, Any],
        branch_2: Branch,
    ) -> None:
        response = await client.schema.load(
            schemas=[schema_04_generic_and_node_uniqueness_failure], branch=branch_2.name
        )
        assert not response.errors

        boomer_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["boomer"]
        )
        boomer_main.favorite_color.value = "green"  # type: ignore[attr-defined]
        await boomer_main.save(db=db)
        athena_branch = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=CYLON_KIND, id=initial_dataset["athena"], branch=branch_2
        )
        athena_branch.favorite_color.value = "green"  # type: ignore[attr-defined]
        await athena_branch.save(db=db)
        starbuck_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=PERSON_KIND, id=initial_dataset["starbuck"]
        )
        starbuck_main.favorite_color.value = "purple"  # type: ignore[attr-defined]
        await starbuck_main.save(db=db)
        president_branch = await NodeManager.get_one_by_id_or_default_filter(
            db=db, kind=PERSON_KIND, id=initial_dataset["president"], branch=branch_2
        )
        president_branch.favorite_color.value = "purple"  # type: ignore[attr-defined]
        await president_branch.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.branch.rebase(branch_name=branch_2.name)

        assert initial_dataset["gaius"] not in exc.value.message
        assert initial_dataset["caprica"] not in exc.value.message
        for node in [boomer_main, athena_branch]:
            # boomer_main,
            # athena_branch,
            # starbuck_main,
            # president_branch,
            display_label = await node.get_display_label()
            kind = "TestingHumanoid"
            for field in ("name", "favorite_color"):
                value = getattr(node, field).value
                expected_error_msg = (
                    f"Node-level 'uniqueness_constraints' constraint violation on schema '{kind}'."
                    f" Node ({display_label}) is not compliant."
                    f" The error relates to field {field}.value='{value}'"
                )
                assert expected_error_msg in exc.value.errors[0]["message"]

        for node in [boomer_main, athena_branch]:
            display_label = await node.get_display_label()
            kind = "TestingCylon"
            for field in ("model_number", "favorite_color"):
                value = getattr(node, field).value
                expected_error_msg = (
                    f"Node-level 'uniqueness_constraints' constraint violation on schema '{kind}'."
                    f" Node ({display_label}) is not compliant."
                    f" The error relates to field {field}.value='{value}'"
                )
                assert expected_error_msg in exc.value.errors[0]["message"]

        for node in [starbuck_main, president_branch]:
            display_label = await node.get_display_label()
            kind = "TestingPerson"
            for field in ("homeworld", "favorite_color"):
                value = getattr(node, field).value
                expected_error_msg = (
                    f"Node-level 'uniqueness_constraints' constraint violation on schema '{kind}'."
                    f" Node ({display_label}) is not compliant."
                    f" The error relates to field {field}.value='{value}'"
                )
                assert expected_error_msg in exc.value.errors[0]["message"]

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
