import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.schema.main import AttributeKind, AttributeSchema, NodeSchema, SchemaRoot
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.schemas.car_person import (
    NAMESPACE,
    TESTING_MANUFACTURER,
    TESTING_PERSON,
    SchemaCarPerson,
)

CURRENT_DIRECTORY = Path(__file__).parent.resolve()

SCHEMA_CHANGES_QUERY = """
query {
  InfrahubSchemaChange {
    edges {
      node {
        summary
        status
        applications {
          count
          edges {
            node {
              status
              migrations { count edges { node { migration_name schema_kind status } } }
            }
          }
        }
      }
    }
  }
}
"""

pytestmark = pytest.mark.shard_b

SET_OWNERS = """
mutation SetOwners($id: String!, $owners: [MetadataNodeInput!]) {
  TestingManufacturerUpdate(
    data: {
      id: $id
      description: { value: "kept", owners: $owners }
      node_metadata: { owners: $owners, field_owners: [{ field: "customers", owners: $owners }] }
    }
  ) {
    ok
  }
}
"""

OWNERS_QUERY = """
query Owners($ids: [ID]) {
  %(kind)s(ids: $ids) {
    edges {
      node {
        %(attribute)s { value ownership { state owners { id } } }
        customers { ownership { state owners { id } } }
      }
      node_metadata { ownership { state owners { id } } }
    }
  }
}
"""


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

        device_interface = await client.schema.load(schemas=[device_and_interface_schema], branch=device_branch.name)
        assert device_interface.schema_updated
        # Validate that the schema is in sync after loading the device and interface schema
        assert await self.schema_in_sync(client=client, branch=device_branch.name)

        delete_interface = await client.schema.load(schemas=[delete_interface_schema], branch=device_branch.name)
        assert delete_interface.schema_updated
        # Validate that the schema is in sync after removing the interface
        assert await self.schema_in_sync(client=client, branch=device_branch.name)

        schema_changes = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name=device_branch.name)
        assert schema_changes["InfrahubSchemaChange"]["edges"] == [
            {
                "node": {
                    "summary": "networkinterface_remove",
                    "status": "APPLIED",
                    "applications": {
                        "count": 1,
                        "edges": [
                            {
                                "node": {
                                    "status": "APPLIED",
                                    "migrations": {
                                        "count": 1,
                                        "edges": [
                                            {
                                                "node": {
                                                    "migration_name": "node.remove",
                                                    "schema_kind": "NetworkInterface",
                                                    "status": "APPLIED",
                                                }
                                            }
                                        ],
                                    },
                                }
                            }
                        ],
                    },
                }
            },
            {
                "node": {
                    "summary": "networkdevice_add_and_1_more",
                    "status": "APPLIED",
                    "applications": {
                        "count": 1,
                        "edges": [{"node": {"status": "APPLIED", "migrations": {"count": 0, "edges": []}}}],
                    },
                }
            },
        ]

    async def test_owners_follow_a_renamed_attribute_and_a_changed_kind(
        self, default_branch: str, client: InfrahubClient, schema_base: SchemaRoot
    ) -> None:
        async def read_owners(kind: str, attribute: str) -> dict[str, Any]:
            response = await client.execute_graphql(
                query=OWNERS_QUERY % {"kind": kind, "attribute": attribute},
                variables={"ids": [manufacturer.id]},
                branch_name=default_branch,
            )
            return response[kind]["edges"][0]

        async def load(schema: dict[str, Any]) -> None:
            response = await client.schema.load(schemas=[schema], branch=default_branch)
            assert response.errors == {}
            # A worker can refuse a query while it loads the new schema, and this wait tries again.
            assert await self.schema_in_sync(client=client, branch=default_branch)

        group = await client.create(kind="CoreAccountGroup", name="migration-owners", branch=default_branch)
        await group.save()
        manufacturer = await client.create(kind=TESTING_MANUFACTURER, name="Owned Maker", branch=default_branch)
        await manufacturer.save()
        owners = [{"id": group.id}]
        response = await client.execute_graphql(
            query=SET_OWNERS, variables={"id": manufacturer.id, "owners": owners}, branch_name=default_branch
        )
        assert response == {"TestingManufacturerUpdate": {"ok": True}}
        ownership = {"ownership": {"state": "OWNERS", "owners": owners}}

        def owned(attribute: str) -> dict[str, Any]:
            return {
                "node": {attribute: {"value": "kept"} | ownership, "customers": ownership},
                "node_metadata": ownership,
            }

        assert await read_owners(kind=TESTING_MANUFACTURER, attribute="description") == owned("description")

        # The ID of the attribute and of the node make the load a rename, and not a removal with an addition.
        current = await client.schema.get(kind=TESTING_MANUFACTURER, branch=default_branch, refresh=True)
        schema = schema_base.to_schema_dict()
        manufacturer_schema = next(node for node in schema["nodes"] if node["name"] == "Manufacturer")
        description = next(attr for attr in manufacturer_schema["attributes"] if attr["name"] == "description")
        description["id"] = next(attr.id for attr in current.attributes if attr.name == "description")
        description["name"] = "details"
        await load(schema=schema)

        assert await read_owners(kind=TESTING_MANUFACTURER, attribute="details") == owned("details")

        manufacturer_schema["id"] = current.id
        manufacturer_schema["name"] = "CarMaker"
        for node in schema["nodes"]:
            for relationship in node["relationships"]:
                if relationship["peer"] == TESTING_MANUFACTURER:
                    relationship["peer"] = f"{NAMESPACE}CarMaker"
        await load(schema=schema)

        assert await read_owners(kind=f"{NAMESPACE}CarMaker", attribute="details") == owned("details")

    @staticmethod
    async def schema_in_sync(client: InfrahubClient, branch: str | None, wait_for_seconds: int = 30) -> bool:
        SCHEMA_HASH_SYNC_STATUS = """
        query {
        InfrahubStatus {
            summary {
            schema_hash_synced
            }
        }
        }
        """
        deadline = time.monotonic() + wait_for_seconds
        last_error: GraphQLError | None = None
        while True:
            try:
                response = await client.execute_graphql(query=SCHEMA_HASH_SYNC_STATUS, branch_name=branch)
                if response["InfrahubStatus"]["summary"]["schema_hash_synced"]:
                    return True
            except GraphQLError as exc:
                last_error = exc

            if time.monotonic() >= deadline:
                if last_error is not None:
                    client.log.warning(f"schema_in_sync timed out; last suppressed GraphQLError: {last_error.errors}")
                return False

            await asyncio.sleep(1)
