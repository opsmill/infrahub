import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from infrahub_sdk import InfrahubClient

from infrahub.testing.helpers import TestInfrahubDev
from infrahub.testing.schemas.car_person import (
    NAMESPACE,
    TESTING_PERSON,
    SchemaCarPerson,
)

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestSchemaMigrations(TestInfrahubDev, SchemaCarPerson):
    @pytest.fixture(scope="class")
    def schema_person_mandatory_age(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person = copy.deepcopy(schema_person_base)
        schema_person["attributes"].append({"name": "age", "kind": "Number", "optional": False, "default_value": 99})
        return schema_person

    @pytest.fixture(scope="class")
    def schema_person_with_age(
        self,
        schema_car_base: dict[str, Any],
        schema_person_mandatory_age: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_mandatory_age, schema_car_base, schema_manufacturer_base],
        }

    async def test_setup_initial_schema(
        self, default_branch: str, infrahub_client: InfrahubClient, schema_base: dict[str, Any]
    ) -> None:
        await infrahub_client.schema.wait_until_converged(branch=default_branch)
        # Validate that the schema is in sync after initial startup
        assert await self.schema_in_sync(client=infrahub_client, branch=default_branch)
        resp = await infrahub_client.schema.load(
            schemas=[schema_base], branch=default_branch, wait_until_converged=True
        )
        assert resp.errors == {}

        await infrahub_client.schema.wait_until_converged(branch=default_branch)
        await infrahub_client.schema.fetch(branch=default_branch, namespaces=[NAMESPACE])
        _ = await infrahub_client.schema.get(kind=TESTING_PERSON, branch=default_branch)

        _ = await self.create_persons(client=infrahub_client, branch=default_branch)
        _ = await self.create_manufacturers(client=infrahub_client, branch=default_branch)

        assert True

    async def test_update_schema(self, infrahub_client: InfrahubClient, schema_person_with_age: dict[str, Any]) -> None:
        branch = await infrahub_client.branch.create(branch_name="branch2")
        resp = await infrahub_client.schema.load(schemas=[schema_person_with_age], branch=branch.name)

        assert resp.errors == {}

    async def test_schema_load_and_delete(self, infrahub_client: InfrahubClient) -> None:
        with Path(CURRENT_DIRECTORY / "test_files/device_and_interface_schema.yml").open(encoding="utf-8") as file:
            device_and_interface_schema = yaml.safe_load(file.read())

        with Path(CURRENT_DIRECTORY / "test_files/delete_interface_schema.yml").open(encoding="utf-8") as file:
            delete_interface_schema = yaml.safe_load(file.read())

        device_branch = await infrahub_client.branch.create(branch_name="device_branch")

        device_interface = await infrahub_client.schema.load(
            schemas=[device_and_interface_schema], branch=device_branch.name, wait_until_converged=True
        )
        assert device_interface.schema_updated
        # Validate that the schema is in sync after loading the device and interface schema
        assert await self.schema_in_sync(client=infrahub_client, branch=device_branch.name)

        delete_interface = await infrahub_client.schema.load(
            schemas=[delete_interface_schema], branch=device_branch.name, wait_until_converged=True
        )
        assert delete_interface.schema_updated
        # Validate that the schema is in sync after removing the interface
        assert await self.schema_in_sync(client=infrahub_client, branch=device_branch.name)

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
