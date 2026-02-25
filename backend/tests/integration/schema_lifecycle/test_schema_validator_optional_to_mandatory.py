from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema

from .shared import TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase


class TestSchemaLifecycleOptionalToMandatory(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_person_with_default_height(self) -> SchemaRoot:
        schema = copy.deepcopy(CAR_SCHEMA)
        schema.version = "1.0"

        person = schema.get(name=TestKind.PERSON)
        person.get_attribute(name="height").default_value = 180

        return schema

    @pytest.fixture(scope="class")
    def schema_person_mandatory_height_no_default(self, schema_person_with_default_height: SchemaRoot) -> SchemaRoot:
        """Height becomes mandatory (optional=False) AND default_value is cleared."""
        schema = copy.deepcopy(schema_person_with_default_height)
        person = schema.get(name=TestKind.PERSON)

        height_attr = person.get_attribute(name="height")
        height_attr.optional = False
        height_attr.default_value = None

        return schema

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_person_with_default_height: SchemaRoot
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_person_with_default_height, update_db=True)

        alice = await Node.init(schema=TestKind.PERSON, db=db)
        await alice.new(db=db, name="Alice", height=170)
        await alice.save(db=db)

        # Bob gets the default height (180)
        bob = await Node.init(schema=TestKind.PERSON, db=db)
        await bob.new(db=db, name="Bob")
        await bob.save(db=db)

        return {"alice": alice.id, "bob": bob.id}

    async def test_baseline(
        self, client: InfrahubClient, db: InfrahubDatabase, initial_dataset: dict[str, str]
    ) -> None:
        person_schema = registry.schema.get(name=TestKind.PERSON, duplicate=False)
        height_attr = person_schema.get_attribute(name="height")
        assert height_attr.optional is True
        assert height_attr.default_value == 180

        persons = await registry.manager.query(db=db, schema=TestKind.PERSON)
        assert len(persons) == 2

    async def test_check_mandatory_no_default_succeeds_when_all_have_values(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_person_mandatory_height_no_default: SchemaRoot,
    ) -> None:
        """Making height mandatory after clearing default_value should pass because no existing objects have null height."""
        success, _ = await client.schema.check(
            schemas=[schema_person_mandatory_height_no_default.model_dump(mode="json")]
        )
        assert success

    async def test_load_mandatory_no_default_succeeds(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_person_mandatory_height_no_default: SchemaRoot,
    ) -> None:
        """Loading the mandatory schema should succeed."""
        branch = await client.branch.create(branch_name="mandatory-height")
        response = await client.schema.load(
            schemas=[schema_person_mandatory_height_no_default.model_dump(mode="json")], branch=branch.name
        )
        assert not response.errors
        assert response.schema_updated

        person_schema = registry.schema.get(name=TestKind.PERSON, branch=branch.name, duplicate=False)
        height_attr = person_schema.get_attribute(name="height")
        assert height_attr.optional is False
        assert height_attr.default_value is None

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
