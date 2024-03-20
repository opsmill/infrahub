from typing import Any, Dict

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
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


class TestSchemaLifecycleValidatorRebase(TestSchemaLifecycleBase):
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
            db=db, name="accord", description="Honda Accord", color="#3443eb", manufacturer=honda, owner=jane
        )
        await accord.save(db=db)

        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(db=db, name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=john)
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
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch_2")

    @pytest.fixture(scope="class")
    def schema_01_person_name_regex(self, schema_person_base) -> Dict[str, Any]:
        """Add regex to TestPerson.name that does not fit existing data"""
        new_schema = {**schema_person_base}
        new_schema["attributes"][0]["regex"] = "^[A-Z][a-z]+$"
        return new_schema

    @pytest.fixture(scope="class")
    def schema_01_attr_regex(
        self, schema_car_base, schema_01_person_name_regex, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_01_person_name_regex, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_02_car_unique(self, schema_car_base) -> Dict[str, Any]:
        new_schema = {**schema_car_base}
        new_schema["uniqueness_constraints"] = [["owner", "manufacturer"]]
        return new_schema

    @pytest.fixture(scope="class")
    def schema_02_node_unique(
        self, schema_car_base, schema_person_base, schema_02_car_unique, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_car_base, schema_02_car_unique, schema_tag_base],
        }

    async def test_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        cars = await registry.manager.query(db=db, schema=CAR_KIND)
        tags = await registry.manager.query(db=db, schema=TAG_KIND)
        assert len(persons) == 2
        assert len(cars) == 3
        assert len(tags) == 2

    async def test_step_01_attr_regex_add_rebase_failure(
        self, client: InfrahubClient, db: InfrahubDatabase, initial_dataset, schema_01_attr_regex, branch_2
    ):
        success, _ = await client.schema.load(schemas=[schema_01_attr_regex])
        assert success
        little_john = await Node.init(schema=PERSON_KIND, db=db, branch=branch_2)
        await little_john.new(db=db, name="little john", height=115, description="a smaller john")
        await little_john.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.branch.rebase(branch_name=branch_2.name)

            assert little_john.id in exc.value
            assert "attribute.regex.update" in exc.value

    async def test_step_02_node_unique_rebase_failure(
        self, client: InfrahubClient, db: InfrahubDatabase, initial_dataset, schema_02_node_unique, branch_2
    ):
        success, _ = await client.schema.load(schemas=[schema_02_node_unique])
        assert success

        honda = await client.get(id=initial_dataset["honda"], kind=MANUFACTURER_KIND_01, branch=branch_2.name)
        jane = await client.get(id=initial_dataset["jane"], kind=PERSON_KIND, branch=branch_2.name)

        another_civic = await client.create(
            kind=CAR_KIND,
            branch=branch_2.name,
            name="civic2",
            description="Honda Civic2",
            color="#c9eb35",
            manufacturer=honda,
            owner=jane,
        )
        await another_civic.save()

        exc = None
        with pytest.raises(GraphQLError) as exc:
            await client.branch.rebase(branch_name=branch_2.name)

        assert initial_dataset["honda"] in exc.value
        assert "node.uniqueness_constraints.update" in exc.value
