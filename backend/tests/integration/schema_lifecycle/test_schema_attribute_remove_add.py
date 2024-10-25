from typing import Any, Optional

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import InitializationError

from ..shared import load_schema
from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    PERSON_KIND,
    TAG_KIND,
    TestSchemaLifecycleBase,
)

# pylint: disable=unused-argument


class BranchState:
    def __init__(self) -> None:
        self._branch: Optional[Branch] = None

    @property
    def branch(self) -> Branch:
        if self._branch:
            return self._branch
        raise InitializationError

    @branch.setter
    def branch(self, value: Branch) -> None:
        self._branch = value


state = BranchState()


# ---------------------------------
# This test was initially written to troubleshoot and fix https://github.com/opsmill/infrahub/issues/4727
# The issue was primarily happening in Main
# ---------------------------------
class TestSchemaLifecycleAttributeRemoveAddMain(TestSchemaLifecycleBase):
    @property
    def branch1(self) -> Branch:
        return state.branch

    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry, schema_step01):
        await load_schema(db=db, schema=schema_step01)

        # Load data in the MAIN branch first
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, firstname="John", lastname="Doe", height=175, description="The famous Joe Doe")
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

        objs = {
            "john": john.id,
            "renault": renault.id,
            "megane": megane.id,
            "clio": clio.id,
            "red": red.id,
        }

        return objs

    @pytest.fixture(scope="class")
    def schema_step01(
        self, schema_car_base, schema_person_02_first_last, schema_manufacturer_base, schema_tag_base
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_02_first_last, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_step02(
        self, schema_car_base, schema_person_03_no_height, schema_manufacturer_base, schema_tag_base
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_03_no_height, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_step03(
        self, schema_car_base, schema_person_02_first_last, schema_manufacturer_base, schema_tag_base
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_person_02_first_last,
                schema_car_base,
                schema_manufacturer_base,
                schema_tag_base,
            ],
        }

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        persons = await registry.manager.query(db=db, schema=PERSON_KIND)
        assert len(persons) == 1

    async def test_step02_check_attr_add_rename(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02
    ):
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

    async def test_step02_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step02):
        response = await client.schema.load(schemas=[schema_step02])
        assert not response.errors

        # Ensure that we can query the nodes with the new schema in BRANCH1
        persons = await registry.manager.query(
            db=db,
            schema=PERSON_KIND,
            filters={"firstname__value": "John"},  # , branch=self.branch1
        )
        assert len(persons) == 1
        john = persons[0]
        assert john.firstname.value == "John"  # type: ignore[attr-defined]
        assert not hasattr(john, "height")

    async def test_step03_check(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        success, response = await client.schema.check(schemas=[schema_step03])
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {"added": {"height": None}, "changed": {}, "removed": {}},
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        }
        assert success

    async def test_step03_load(self, db: InfrahubDatabase, client: InfrahubClient, initial_dataset, schema_step03):
        response = await client.schema.load(schemas=[schema_step03])
        assert not response.errors

        # Modify the value for Height in the database
        persons = await registry.manager.query(
            db=db,
            schema=PERSON_KIND,
            filters={"firstname__value": "John"},
        )
        assert len(persons) == 1
        john = persons[0]
        assert john.height.value is None
        john.height.value = 200
        await john.save(db=db)

        # Validate that the new value has been properly saved
        persons2 = await registry.manager.query(
            db=db,
            schema=PERSON_KIND,
            filters={"firstname__value": "John"},
        )
        assert len(persons2) == 1
        john2 = persons2[0]
        assert john2.height.value == 200
