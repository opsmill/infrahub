import pytest

from infrahub.core.schema import core_models
from infrahub_client import Config, InfrahubClient
from infrahub_client.schema import NodeSchema

from .conftest import InfrahubTestClient

# pylint: disable=unused-argument


class TestInfrahubSchema:
    @pytest.fixture(scope="class")
    async def client(self):
        # pylint: disable=import-outside-toplevel
        from infrahub.server import app

        return InfrahubTestClient(app)

    async def test_schema_all(self, client, init_db_base):
        config = Config(requester=client.async_request)
        ifc = await InfrahubClient.init(config=config)
        schema_nodes = await ifc.schema.all()

        assert len(schema_nodes) == len(core_models["nodes"])
        assert "BuiltinLocation" in schema_nodes
        assert isinstance(schema_nodes["BuiltinLocation"], NodeSchema)

    async def test_schema_get(self, client, init_db_base):
        ifc = await InfrahubClient.init(test_client=client)
        schema_node = await ifc.schema.get(kind="BuiltinLocation")

        assert isinstance(schema_node, NodeSchema)
        assert ifc.default_branch in ifc.schema.cache
        assert len(ifc.schema.cache[ifc.default_branch]) == len(core_models["nodes"])
