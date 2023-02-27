from infrahub_client import InfrahubClient
from infrahub_client.schema import NodeSchema


async def test_fetch_schema(mock_schema_query_01):  # pylint: disable=unused-argument
    client = await InfrahubClient.init(address="http://mock", insert_tracker=True)
    nodes = await client.schema.fetch(branch="main")

    assert len(nodes) == 3
    assert sorted(nodes.keys()) == ["GraphQLQuery", "Repository", "Tag"]
    assert isinstance(nodes["Tag"], NodeSchema)
