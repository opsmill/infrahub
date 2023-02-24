import pytest
from fastapi.testclient import TestClient

from infrahub_client import InfrahubClient, InfrahubNode

# pylint: disable=unused-argument


class TestInfrahubNode:
    @pytest.fixture(scope="class")
    async def client(self):
        # pylint: disable=import-outside-toplevel
        from infrahub.main import app

        return TestClient(app)

    async def test_node_create(self, client, init_db_base, location_schema):
        ifc = await InfrahubClient.init(test_client=client)
        data = {"name": {"value": "JFK1"}, "description": {"value": "JFK Airport"}, "type": {"value": "SITE"}}
        node = InfrahubNode(client=ifc, schema=location_schema, data=data)
        await node.save()

        assert node.id is not None
