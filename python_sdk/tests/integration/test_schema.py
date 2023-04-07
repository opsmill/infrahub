import pytest
from fastapi.testclient import TestClient

from infrahub_client import InfrahubClient
from infrahub_client.schema import NodeSchema

# pylint: disable=unused-argument


class TestInfrahubSchema:
    @pytest.fixture(scope="class")
    async def client(self):
        # pylint: disable=import-outside-toplevel
        from infrahub.api.main import app

        return TestClient(app)

    async def test_schema_all(self, client, init_db_base):
        ifc = await InfrahubClient.init(test_client=client)
        schema_nodes = await ifc.schema.all()

        assert len(schema_nodes) == 19
        assert "Location" in schema_nodes
        assert isinstance(schema_nodes["Location"], NodeSchema)

    async def test_schema_get(self, client, init_db_base):
        ifc = await InfrahubClient.init(test_client=client)
        schema_node = await ifc.schema.get(kind="Location")

        assert isinstance(schema_node, NodeSchema)
        assert ifc.default_branch in ifc.schema.cache
        assert len(ifc.schema.cache[ifc.default_branch]) == 19
