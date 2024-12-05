import copy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.testing.helpers import TestInfrahubDev
from infrahub.testing.schemas.car_person import (
    NAMESPACE,
    TESTING_PERSON,
    SchemaCarPerson,
)


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
