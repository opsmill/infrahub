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

from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    PERSON_KIND,
    TAG_KIND,
    TestSchemaLifecycleBase,
    load_schema,
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
    def schema_person_tag(self, schema_person_base) -> Dict[str, Any]:
        schema_person_base["relationships"] = [
            {
                "name": "tags",
                "kind": "Generic",
                "optional": True,
                "peer": "TestingTag",
                "cardinality": "many",
            }
        ]
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_car_main_driver(self, schema_car_base) -> Dict[str, Any]:
        assert schema_car_base["relationships"][0]["name"] == "owner"
        schema_car_base["relationships"][0]["name"] = "main_driver"
        return schema_car_base

    @pytest.fixture(scope="class")
    def schema_tag_no_persons(self, schema_tag_base) -> Dict[str, Any]:
        assert schema_tag_base["relationships"][1]["name"] == "persons"
        schema_tag_base["relationships"][0]["state"] = "absent"
        return schema_tag_base

    @pytest.fixture(scope="class")
    def schema_step02(
        self, schema_car_main_driver, schema_person_tag, schema_manufacturer_base, schema_tag_base
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_tag, schema_car_main_driver, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_step03(
        self, schema_car_main_driver, schema_person_tag, schema_manufacturer_base, schema_tag_no_persons
    ) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_tag, schema_car_main_driver, schema_manufacturer_base, schema_tag_no_persons],
        }

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, branch=self.branch1)
        assert len(persons) == 3

    async def test_step02_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02):
        car_schema = registry.schema.get_node_schema(name=CAR_KIND)
        rel = car_schema.get_relationship(name="owner")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step02["nodes"][1]["name"] == "Car"
        assert schema_step02["nodes"][1]["relationships"][0]["name"] == "main_driver"
        schema_step02["nodes"][1]["relationships"][0]["id"] = rel.id

        success, response = await client.schema.check(schemas=[schema_step02], branch=self.branch1.name)

        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingCar": {
                        "added": {},
                        "changed": {
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "main_driver": {
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
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "relationships": {
                                "added": {"tags": None},
                                "changed": {},
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        }
        assert success

    async def test_step02_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02):
        car_schema = registry.schema.get_node_schema(name=CAR_KIND)
        rel = car_schema.get_relationship(name="owner")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step02["nodes"][1]["name"] == "Car"
        assert schema_step02["nodes"][1]["relationships"][0]["name"] == "main_driver"
        schema_step02["nodes"][1]["relationships"][0]["id"] = rel.id

        # Load the new schema and apply the migrations
        success, response = await client.schema.load(schemas=[schema_step02], branch=self.branch1.name)
        assert success
        assert response is None

        # Check if the branch has been properly updated
        branches = await client.branch.all()
        assert branches[self.branch1.name].is_isolated is True
        assert branches[self.branch1.name].has_schema_changes is True

        # Ensure that we can query the nodes with the new schema in BRANCH1
        john_cars = await registry.manager.query(
            db=db, schema=CAR_KIND, filters={"main_driver__name__value": "John"}, branch=self.branch1
        )
        assert len(john_cars) == 2
        john = await john_cars[0].main_driver.get_peer(db=db)  # type: ignore[attr-defined]
        assert john.id == initial_dataset["john"]
        tags = await john.tags.get_peers(db=db)
        assert len(tags) == 2

        # And ensure that we can still query them with the original schema in MAIN
        john_cars_main = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"main_driver__name__value": "John"}
        )
        assert len(john_cars_main) == 2

    async def test_step03_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        success, response = await client.schema.check(schemas=[schema_step03], branch=self.branch1.name)
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingTag": {
                        "added": {},
                        "changed": {
                            "relationships": {
                                "added": {},
                                "changed": {},
                                "removed": {"cars": None},
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

        john = await registry.manager.get_one(db=db, id=initial_dataset["john"], branch=self.branch1)
        assert john
        tags = await john.tags.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(tags) == 2

        # FIXME
        # red_branch = await registry.manager.get_one(db=db, id=initial_dataset["red"], branch=self.branch1)
        # assert not hasattr(red_branch, "persons")

        red_main = await registry.manager.get_one(db=db, id=initial_dataset["red"])
        assert red_main
        persons = await red_main.persons.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(persons) == 1

    async def test_rebase(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        branch = await client.branch.rebase(branch_name=self.branch1.name)
        assert branch

        # Ensure that we can query the nodes with the new schema in BRANCH1
        jane_cars = await registry.manager.query(
            db=db, schema=CAR_KIND, filters={"main_driver__name__value": "Jane"}, branch=self.branch1
        )
        assert len(jane_cars) == 2
        jane = await jane_cars[0].main_driver.get_peer(db=db)  # type: ignore[attr-defined]
        assert jane.id == initial_dataset["jane"]
        tags = await jane.tags.get_peers(db=db)
        assert len(tags) == 1

    async def test_merge(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        branch = await client.branch.merge(branch_name=self.branch1.name)
        assert branch

        # Ensure that we can query the nodes with the new schema in MAIN
