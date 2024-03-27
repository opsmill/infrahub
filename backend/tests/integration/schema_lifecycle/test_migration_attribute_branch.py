from typing import Any, Dict

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_branch,
)
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


class TestSchemaLifecycleAttributeBranch(TestSchemaLifecycleBase):
    @property
    def branch1(self) -> Branch:
        return pytest.state["branch1"]  # type: ignore[index]

    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry, schema_step01):
        await load_schema(db=db, schema=schema_step01)

        # Load data in the MAIN branch first
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

        renault = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await renault.new(
            db=db, name="renault", description="Groupe Renault is a French multinational automobile manufacturer"
        )
        await renault.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(
            db=db, name="Megane", description="Renault Megane", color="#c93420", manufacturer=renault, owner=john
        )
        await megane.save(db=db)

        clio = await Node.init(schema=CAR_KIND, db=db)
        await clio.new(
            db=db, name="Clio", description="Renault Clio", color="#ff3420", manufacturer=renault, owner=john
        )
        await clio.save(db=db)

        red = await Node.init(schema=TAG_KIND, db=db)
        await red.new(db=db, name="red", persons=[john])
        await red.save(db=db)

        # Create Branch1
        branch1 = await create_branch(db=db, branch_name="branch1")
        pytest.state = {"branch1": branch1}

        # Load data in BRANCH1
        richard = await Node.init(schema=PERSON_KIND, db=db, branch=branch1)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

        mercedes = await Node.init(schema=MANUFACTURER_KIND_01, db=db, branch=branch1)
        await mercedes.new(
            db=db, name="mercedes", description="Mercedes-Benz, commonly referred to as Mercedes and sometimes as Benz"
        )
        await mercedes.save(db=db)

        glc = await Node.init(schema=CAR_KIND, db=db, branch=branch1)
        await glc.new(
            db=db, name="glc", description="Mecedes GLC", color="#3422eb", manufacturer=mercedes, owner=richard
        )
        await glc.save(db=db)

        green = await Node.init(schema=TAG_KIND, db=db, branch=branch1)
        await green.new(db=db, name="green", persons=[john, richard])
        await green.save(db=db)

        # Create Data in MAIN after BRANCH1 was created
        jane = await Node.init(schema=PERSON_KIND, db=db)
        await jane.new(db=db, name="Jane", height=165, description="The famous Jane Doe")
        await jane.save(db=db)

        honda = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await honda.new(db=db, name="honda", description="Honda Motor Co., Ltd")
        await honda.save(db=db)

        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(
            db=db, name="accord", description="Honda Accord", color="#3443eb", manufacturer=honda, owner=jane
        )
        await accord.save(db=db)

        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(db=db, name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=jane)
        await civic.save(db=db)

        blue = await Node.init(schema=TAG_KIND, db=db)
        await blue.new(db=db, name="blue", cars=[accord, civic], persons=[jane])
        await blue.save(db=db)

        objs = {
            "john": john.id,
            "jane": jane.id,
            "richard": richard.id,
            "honda": honda.id,
            "renault": renault.id,
            "mercedes": mercedes.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
            "clio": clio.id,
            "glc": glc.id,
            "blue": blue.id,
            "red": red.id,
            "green": green.id,
        }

        return objs

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
        self, schema_car_base, schema_person_03_no_height, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_03_no_height,
                schema_car_base,
                schema_manufacturer_base,
                schema_tag_base,
            ],
        }

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, branch=self.branch1)
        assert len(persons) == 3

    async def test_step02_check_attr_add_rename(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02
    ):
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        success, response = await client.schema.check(schemas=[schema_step02], branch=self.branch1.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {"lastname": None},
                                "changed": {
                                    "firstname": {
                                        "added": {},
                                        "changed": {"name": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        }

    async def test_step02_load_attr_add_rename(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02
    ):
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND, branch=self.branch1)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        # Load the new schema and apply the migrations
        success, response = await client.schema.load(schemas=[schema_step02], branch=self.branch1.name)
        assert success
        assert response is None

        # Check if the branch has been properly updated
        branches = await client.branch.all()
        assert branches[self.branch1.name].is_isolated is True
        assert branches[self.branch1.name].has_schema_changes is True

        # Ensure that we can query the nodes with the new schema in BRANCH1
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"firstname__value": "John"}, branch=self.branch1
        )
        assert len(persons) == 1
        john = persons[0]
        assert john.firstname.value == "John"  # type: ignore[attr-defined]

        # Set a value to the new attribute
        john.lastname.value = "Doe"  # type: ignore[attr-defined]
        await john.save(db=db)

        # And ensure that we can still query them with the original schema in MAIN
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"name__value": "John"})
        assert len(persons) == 1
        john = persons[0]
        assert john.name.value == "John"  # type: ignore[attr-defined]

    async def test_step03_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        success, response = await client.schema.check(schemas=[schema_step03], branch=self.branch1.name)
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {},
                                "removed": {"height": None},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        }
        assert success

    async def test_step03_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        success, response = await client.schema.load(schemas=[schema_step03], branch=self.branch1.name)
        assert response is None
        assert success

        # Ensure that we can query the existing node with the new schema
        # person_schema = registry.schema.get(name=PERSON_KIND)
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"firstname__value": "John"}, branch=self.branch1
        )
        assert len(persons) == 1
        john = persons[0]
        assert not hasattr(john, "height")

    async def test_rebase(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        branch = await client.branch.rebase(branch_name=self.branch1.name)
        assert branch

        # Validate that all data added to main after the creation of the branch has been migrated properly
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"firstname__value": "Jane"}, branch=self.branch1
        )
        assert len(persons) == 1
        jane = persons[0]
        assert not hasattr(jane, "height")

    async def test_merge(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        branch = await client.branch.merge(branch_name=self.branch1.name)
        assert branch

        # Ensure that we can query the nodes with the new schema in MAIN
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"firstname__value": "John"})
        assert len(persons) == 1
        john = persons[0]
        assert john.firstname.value == "John"  # type: ignore[attr-defined]
        assert john.lastname.value == "Doe"  # type: ignore[attr-defined]
        assert not hasattr(john, "height")
        assert not hasattr(john, "name")

        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"firstname__value": "Jane"})
        assert len(persons) == 1
        jane = persons[0]
        assert jane.firstname.value == "Jane"  # type: ignore[attr-defined]
        assert jane.lastname.value is None  # type: ignore[attr-defined]
        assert not hasattr(jane, "height")
        assert not hasattr(jane, "name")
