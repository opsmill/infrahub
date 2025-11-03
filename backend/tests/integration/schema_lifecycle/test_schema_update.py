from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete

from .shared import (
    TestSchemaLifecycleBase,
)

ACCORD_COLOR = "#3443eb"


class TestSchemaLifecycleValidatorMain(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_network(
        self,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Network",
                    "default_filter": "hostname__value",
                    "attributes": [{"name": "hostname", "kind": "Text"}, {"name": "model", "kind": "Text"}],
                },
                {
                    "name": "Interface",
                    "namespace": "Network",
                    "uniqueness_constraints": [["device", "name__value"]],
                    "attributes": [{"name": "name", "kind": "Text", "optional": False}],
                    "relationships": [
                        {
                            "name": "device",
                            "cardinality": "one",
                            "kind": "Parent",
                            "peer": "NetworkDevice",
                            "optional": False,
                        }
                    ],
                },
            ],
        }

    async def test_step_01_create_branch(self, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="test", sync_with_git=False)
        assert branch

    async def test_step_02_load_schema(self, client: InfrahubClient, schema_network) -> None:
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_network], branch="test")
        assert not response.errors

    async def test_step_03_load_data(self, db: InfrahubDatabase, client: InfrahubClient, schema_network) -> None:
        dev1 = await client.create(kind="NetworkDevice", hostname="device", model="switch", branch="test")
        await dev1.save()
        assert dev1.id

        intf1 = await client.create(kind="NetworkInterface", name="interface1", device=dev1.id, branch="test")
        await intf1.save()
        assert intf1.id

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
