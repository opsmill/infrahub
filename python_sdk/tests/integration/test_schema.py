import pytest
from infrahub.core.schema import core_models
from infrahub.server import app

from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.schema import NodeSchema

from .conftest import InfrahubTestClient

# pylint: disable=unused-argument


class TestInfrahubSchema:
    @pytest.fixture(scope="class")
    async def client(self):
        return InfrahubTestClient(app)

    async def test_schema_all(self, client, init_db_base):
        config = Config(requester=client.async_request)
        ifc = await InfrahubClient.init(config=config)
        schema_nodes = await ifc.schema.all()

        nodes = [node for node in core_models["nodes"] if node["namespace"] != "Internal"]
        generics = [node for node in core_models["generics"] if node["namespace"] != "Internal"]

        assert len(schema_nodes) == len(nodes) + len(generics)
        assert "BuiltinTag" in schema_nodes
        assert isinstance(schema_nodes["BuiltinTag"], NodeSchema)

    async def test_schema_get(self, client, init_db_base):
        config = Config(username="admin", password="infrahub", requester=client.async_request)
        ifc = await InfrahubClient.init(config=config)
        schema_node = await ifc.schema.get(kind="BuiltinTag")

        assert isinstance(schema_node, NodeSchema)
        assert ifc.default_branch in ifc.schema.cache
        nodes = [node for node in core_models["nodes"] if node["namespace"] != "Internal"]
        generics = [node for node in core_models["generics"] if node["namespace"] != "Internal"]

        assert len(ifc.schema.cache[ifc.default_branch]) == len(nodes) + len(generics)

    async def test_schema_load_many(self, client, init_db_base, schema_extension_01, schema_extension_02):
        config = Config(username="admin", password="infrahub", requester=client.async_request)
        ifc = await InfrahubClient.init(config=config)
        response = await ifc.schema.load(schemas=[schema_extension_01, schema_extension_02])

        assert response.schema_updated

        schema_nodes = await ifc.schema.all(refresh=True)
        assert "InfraRack" in schema_nodes.keys()
        assert "ProcurementContract" in schema_nodes.keys()
