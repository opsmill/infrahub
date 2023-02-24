from infrahub_client import InfrahubClient
from infrahub_client.models import NodeSchema

# from infrahub_client.schema import InfrahubSchema


async def test_fetch_schema(mock_schema_query_01):  # pylint: disable=unused-argument
    client = await InfrahubClient.init(address="http://mock")
    nodes = await client.schema.fetch(branch="main")

    assert len(nodes) == 3
    assert sorted(nodes.keys()) == ["GraphQLQuery", "Repository", "Tag"]
    assert isinstance(nodes["Tag"], NodeSchema)
