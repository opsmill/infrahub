from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.schema import GenericSchema as SDKGenericSchema

from infrahub.core.registry import registry
from infrahub.core.schema import core_models
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator
    from tests.conftest import TestHelper


class TestLoadSchemaAPI(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        pass

    async def test_schema_load_endpoint_idempotent_simple(
        self, initial_dataset: str, client: InfrahubClient, helper: TestHelper, db: InfrahubDatabase
    ) -> None:
        creation = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert creation.schema_updated
        test_device = await client.schema.get(kind="TestDevice")
        attributes = {attrib.name: attrib.order_weight for attrib in test_device.attributes}
        relationships = {attrib.name: attrib.order_weight for attrib in test_device.relationships}
        assert attributes["name"] == 1000
        assert attributes["description"] == 900
        assert attributes["type"] == 3000
        assert relationships["interfaces"] == 450
        assert relationships["tags"] == 7000

        first_relationship_count = await count_relationships(db=db)
        update = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert not update.schema_updated
        updated_relationship_count = await count_relationships(db=db)

        assert first_relationship_count == updated_relationship_count

    async def test_schema_load_endpoint_idempotent_with_generics(
        self, initial_dataset: str, client: InfrahubClient, helper: TestHelper, db: InfrahubDatabase
    ) -> None:
        creation = await client.schema.load(schemas=[helper.schema_file("infra_w_generics_01.json")])
        assert creation.schema_updated
        assert creation.schema_updated
        first_relationship_count = await count_relationships(db=db)
        update = await client.schema.load(schemas=[helper.schema_file("infra_w_generics_01.json")])
        assert not update.schema_updated
        updated_relationship_count = await count_relationships(db=db)

        assert first_relationship_count == updated_relationship_count

        all_schemas = await client.schema.all(refresh=True)
        generic_schemas = [schema for schema in all_schemas.values() if isinstance(schema, SDKGenericSchema)]

        assert len(generic_schemas) == len(core_models["generics"]) + 1

    async def test_schema_load_existing_node_different_kind(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        schema = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db)
        creation = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert not creation.errors

        modified_schema = helper.schema_file("infra_simple_01.json")
        modified_schema["nodes"].pop(0)
        modified_schema["generics"] = [
            {
                "name": "Device",
                "namespace": "Infra",
                "label": "A generic with the same kind as an existing node in the schema",
            }
        ]

        modification = await client.schema.load(schemas=[modified_schema])
        assert modification.errors
        assert modification.errors["errors"]
        assert len(modification.errors["errors"]) == 1
        error = modification.errors["errors"][0]
        assert (
            error["message"]
            == "InfraDevice already exist in the schema as a Node. Either rename it or delete the existing one."
        )
        assert error["extensions"]["code"] == 422

    async def test_schema_load_endpoint_valid_with_extensions(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        schema = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db)
        simple = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert not simple.errors
        org_schema = registry.schema.get(name="TestingOrganization", branch=default_branch.name)
        initial_nbr_relationships = len(org_schema.relationships)

        extended_schema = await client.schema.load(schemas=[helper.schema_file("infra_w_extensions_01.json")])
        assert not extended_schema.errors
        assert extended_schema.schema_updated

        org_schema = registry.schema.get(name="TestingOrganization", branch=default_branch.name)
        assert len(org_schema.relationships) == initial_nbr_relationships + 1
