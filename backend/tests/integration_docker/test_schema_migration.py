from pathlib import Path

import pytest
import yaml
from infrahub_sdk import InfrahubClient
from infrahub_sdk.schema.main import AttributeKind, AttributeSchema, NodeSchema, SchemaRoot
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.schemas.car_person import (
    NAMESPACE,
    TESTING_PERSON,
    SchemaCarPerson,
)

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestSchemaMigrations(TestInfrahubDockerClient, SchemaCarPerson):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_person_mandatory_age(self, schema_person_base: NodeSchema) -> NodeSchema:
        schema_person = schema_person_base.model_copy(deep=True)
        schema_person.attributes.append(
            AttributeSchema(name="age", kind=AttributeKind.NUMBER, optional=False, default_value=99)
        )
        return schema_person

    @pytest.fixture(scope="class")
    def schema_person_with_age(
        self,
        schema_car_base: NodeSchema,
        schema_person_mandatory_age: NodeSchema,
        schema_manufacturer_base: NodeSchema,
    ) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            nodes=[schema_person_mandatory_age, schema_car_base, schema_manufacturer_base],
        )

    async def test_setup_initial_schema(
        self, default_branch: str, client: InfrahubClient, schema_base: SchemaRoot
    ) -> None:
        await client.schema.wait_until_converged(branch=default_branch)
        # Validate that the schema is in sync after initial startup
        assert await self.schema_in_sync(client=client, branch=default_branch)
        resp = await client.schema.load(
            schemas=[schema_base.to_schema_dict()], branch=default_branch, wait_until_converged=True
        )
        assert resp.errors == {}

        await client.schema.wait_until_converged(branch=default_branch)
        await client.schema.fetch(branch=default_branch, namespaces=[NAMESPACE])
        _ = await client.schema.get(kind=TESTING_PERSON, branch=default_branch)

        _ = await self.create_persons(client=client, branch=default_branch)
        _ = await self.create_manufacturers(client=client, branch=default_branch)

        assert True

    @pytest.mark.xfail(reason="Unable to merge the list for attributes, not all items are supporting _sorting_id")
    async def test_update_schema(self, client: InfrahubClient, schema_person_with_age: SchemaRoot) -> None:
        branch = await client.branch.create(branch_name="branch2")
        resp = await client.schema.load(schemas=[schema_person_with_age.to_schema_dict()], branch=branch.name)

        assert resp.errors == {}

    async def test_schema_load_and_delete(self, client: InfrahubClient) -> None:
        device_and_interface_schema = yaml.safe_load(
            Path(CURRENT_DIRECTORY / "test_files/device_and_interface_schema.yml").read_text(encoding="utf-8")
        )
        delete_interface_schema = yaml.safe_load(
            Path(CURRENT_DIRECTORY / "test_files/delete_interface_schema.yml").read_text(encoding="utf-8")
        )

        device_branch = await client.branch.create(branch_name="device_branch")

        device_interface = await client.schema.load(
            schemas=[device_and_interface_schema], branch=device_branch.name, wait_until_converged=True
        )
        assert device_interface.schema_updated
        # Validate that the schema is in sync after loading the device and interface schema
        assert await self.schema_in_sync(client=client, branch=device_branch.name)

        delete_interface = await client.schema.load(
            schemas=[delete_interface_schema], branch=device_branch.name, wait_until_converged=True
        )
        assert delete_interface.schema_updated
        # Validate that the schema is in sync after removing the interface
        assert await self.schema_in_sync(client=client, branch=device_branch.name)

    @staticmethod
    async def schema_in_sync(client: InfrahubClient, branch: str | None) -> bool:
        SCHEMA_HASH_SYNC_STATUS = """
        query {
        InfrahubStatus {
            summary {
            schema_hash_synced
            }
        }
        }
        """
        response = await client.execute_graphql(query=SCHEMA_HASH_SYNC_STATUS, branch_name=branch)
        return response["InfrahubStatus"]["summary"]["schema_hash_synced"]
