from typing import Any, Dict

import pytest
from infrahub_sdk import InfrahubClient

from .shared import (
    TestSchemaLifecycleBase,
)

# pylint: disable=unused-argument
ACCORD_COLOR = "#3443eb"


class TestSchemaLifecycleValidatorMain(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_network(
        self,
    ) -> Dict[str, Any]:
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

    async def test_step_01_create_branch(self, client: InfrahubClient):
        branch = await client.branch.create(branch_name="test", sync_with_git=False)
        assert branch

    async def test_step_02_load_schema(self, client: InfrahubClient, schema_network):
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_network], branch="test")
        assert not response.errors

    async def test_step_03_load_data(self, client: InfrahubClient, schema_network):
        dev1 = await client.create(kind="NetworkDevice", hostname="device", model="switch", branch="test")
        await dev1.save()
        assert dev1.id

        intf1 = await client.create(kind="NetworkInterface", name="interface1", device=dev1.id, branch="test")
        await intf1.save()
        assert intf1.id
