import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from ..shared import load_schema
from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    MANUFACTURER_KIND_03,
    PERSON_KIND,
    TAG_KIND,
    TestSchemaLifecycleBase,
)

# pylint: disable=unused-argument


class TestSchemaLifecycleMain(TestSchemaLifecycleBase):
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

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        assert len(persons) == 2

    async def test_step02_check_attr_add_rename(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02
    ):
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        success, response = await client.schema.check(schemas=[schema_step02])
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
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        # Load the new schema and apply the migrations
        success, response = await client.schema.load(schemas=[schema_step02])
        assert success
        assert response is None

        # Ensure that we can query the existing node with the new schema
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"firstname__value": "John"})
        assert len(persons) == 1
        john = persons[0]
        assert john.firstname.value == "John"  # type: ignore[attr-defined]

    @pytest.mark.xfail(reason="migrations need updates for profiles")
    async def test_step03_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        manufacturer_schema = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step03["nodes"][2]["name"] == "CarMaker"
        schema_step03["nodes"][2]["id"] = manufacturer_schema.id

        success, response = await client.schema.check(schemas=[schema_step03])
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
                                    "manufacturer": {
                                        "added": {},
                                        "changed": {"peer": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    "TestingCarMaker": {
                        "added": {},
                        "changed": {"label": None, "name": None},
                        "removed": {},
                    },
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

    @pytest.mark.xfail(reason="migrations need updates for profiles")
    async def test_step03_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        manufacturer_schema = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step03["nodes"][2]["name"] == "CarMaker"
        schema_step03["nodes"][2]["id"] = manufacturer_schema.id

        success, response = await client.schema.load(schemas=[schema_step03])
        assert response is None
        assert success

        # Ensure that we can query the existing node with the new schema
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"firstname__value": "John"})
        assert len(persons) == 1
        john = persons[0]
        assert not hasattr(john, "height")

        manufacturers = await registry.manager.query(
            db=db, schema=MANUFACTURER_KIND_03, filters={"name__value": "honda"}
        )
        assert len(manufacturers) == 1
        honda = manufacturers[0]
        honda_cars = await honda.cars.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(honda_cars) == 2

    @pytest.mark.xfail(reason="migrations need updates for profiles")
    async def test_step04_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step04):
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step04["nodes"][3]["name"] == "Tag"
        schema_step04["nodes"][3]["id"] = tag_schema.id

        success, response = await client.schema.check(schemas=[schema_step04])

        assert response == {"diff": {"added": {}, "changed": {}, "removed": {"TestingTag": None}}}
        assert success

    @pytest.mark.xfail(reason="migrations need updates for profiles")
    async def test_step04_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step04):
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step04["nodes"][3]["name"] == "Tag"
        schema_step04["nodes"][3]["id"] = tag_schema.id

        success, response = await client.schema.load(schemas=[schema_step04])
        assert response is None
        assert success

        assert registry.schema.has(name=TAG_KIND) is False
