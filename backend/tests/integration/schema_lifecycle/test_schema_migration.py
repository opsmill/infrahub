import os
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml
from infrahub_sdk import UUIDT, Config, InfrahubClient

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_account,
    create_default_branch,
    create_global_branch,
    create_root_node,
    initialization,
)
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema_manager import SchemaBranch, SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.server import app, app_initialization
from tests.adapters.message_bus import BusSimulator
from tests.helpers.test_client import InfrahubTestClient

# pylint: disable=unused-argument


def read_schema(name: str) -> Dict[str, Any]:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    schema_txt = Path(os.path.join(dir_path, "fixtures", f"{name}.yml")).read_text()
    return yaml.safe_load(schema_txt)


async def load_schema(db: InfrahubDatabase, name: str):
    schema = read_schema(name=name)
    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()
    tmp_schema.load_schema(schema=SchemaRoot(**schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)


API_TOKEN = str(UUIDT())
PERSON_KIND = "TestingPerson"
CAR_KIND = "TestingCar"
MANUFACTURER_KIND_01 = "TestingManufacturer"
MANUFACTURER_KIND_03 = "TestingCarMaker"
TAG_KIND = "TestingTag"


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    def local_storage_dir(self, tmpdir_factory) -> str:
        storage_dir = os.path.join(str(tmpdir_factory.getbasetemp().strpath), "storage")
        os.mkdir(storage_dir)
        # tmpdir_factory.mktemp('storage')

        config.SETTINGS.storage.driver = config.StorageDriver.FileSystemStorage
        config.SETTINGS.storage.local.path_ = storage_dir

        return storage_dir

    @pytest.fixture(scope="class")
    def bus_simulator(self, db: InfrahubDatabase):
        bus = BusSimulator(database=db)
        original = config.OVERRIDE.message_bus
        config.OVERRIDE.message_bus = bus
        yield bus
        config.OVERRIDE.message_bus = original

    @pytest.fixture(scope="class")
    async def default_branch(self, local_storage_dir, db: InfrahubDatabase) -> Branch:
        registry.delete_all()
        await delete_all_nodes(db=db)
        await create_root_node(db=db)
        branch = await create_default_branch(db=db)
        await create_global_branch(db=db)
        registry.schema = SchemaManager()
        return branch

    @pytest.fixture(scope="class")
    async def register_internal_schema(self, default_branch: Branch) -> SchemaBranch:
        schema = SchemaRoot(**internal_schema)
        schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    async def register_core_schema(self, default_branch: Branch, register_internal_schema) -> SchemaBranch:
        schema = SchemaRoot(**core_models)
        schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    async def initialize_infrahub(self, db: InfrahubDatabase, register_core_schema, bus_simulator):
        await create_account(
            db=db,
            name="admin",
            password=config.SETTINGS.security.initial_admin_password,
            create_token=True,
            token_value=API_TOKEN,
        )
        await load_schema(db=db, name="step01")
        await initialization(db=db)

    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_infrahub):
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

    @pytest.fixture(scope="class")
    async def test_client(
        self,
        initialize_infrahub,
    ) -> InfrahubTestClient:
        await app_initialization(app)
        return InfrahubTestClient(app=app)

    @pytest.fixture
    async def client(self, test_client: InfrahubTestClient):
        config = Config(api_token=API_TOKEN, requester=test_client.async_request)

        return await InfrahubClient.init(config=config)

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        assert len(persons) == 2

    async def test_step02_check_attr_add_rename(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema02 = read_schema(name="step02")
        schema02["nodes"][0]["attributes"][0]["id"] = attr.id

        success, response = await client.schema.check(schemas=[schema02])
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingCar": {"added": {}, "changed": {"filters": None}, "removed": {}},
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
                            "filters": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        }

    async def test_step02_load_attr_add_rename(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema02 = read_schema(name="step02")
        schema02["nodes"][0]["attributes"][0]["id"] = attr.id

        # Load the new schema and apply the migrations
        success, response = await client.schema.load(schemas=[schema02])
        assert success
        assert response is None

        # Ensure that we can query the existing node with the new schema
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"firstname__value": "John"})
        assert len(persons) == 1
        john = persons[0]
        assert john.firstname.value == "John"  # type: ignore[attr-defined]

    async def test_step03_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        manufacturer_schema = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema03 = read_schema(name="step03")
        assert schema03["nodes"][2]["name"] == "CarMaker"
        schema03["nodes"][2]["id"] = manufacturer_schema.id

        success, response = await client.schema.check(schemas=[schema03])
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingCar": {
                        "added": {},
                        "changed": {
                            "filters": None,
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
                            "filters": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        }
        assert success

    async def test_step03_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset):
        manufacturer_schema = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema03 = read_schema(name="step03")
        assert schema03["nodes"][2]["name"] == "CarMaker"
        schema03["nodes"][2]["id"] = manufacturer_schema.id

        success, response = await client.schema.load(schemas=[schema03])
        assert response is None
        assert success

        # Ensure that we can query the existing node with the new schema
        # person_schema = registry.schema.get(name=PERSON_KIND)
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
