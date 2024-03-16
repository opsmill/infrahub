from infrahub_sdk import InfrahubClient
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter


async def test_schema_sorter(client: InfrahubClient, mock_schema_query_01):
    schemas = await client.schema.all()
    topological_sorter = InfrahubSchemaTopologicalSorter()

    result = topological_sorter.get_sorted_node_schema(schemas=schemas.values())
    assert result == [{"BuiltinLocation", "BuiltinTag", "CoreGraphQLQuery", "CoreRepository"}]

    result = topological_sorter.get_sorted_node_schema(schemas=schemas.values(), required_relationships_only=False)
    assert result == [{"BuiltinTag"}, {"BuiltinLocation", "CoreGraphQLQuery"}, {"CoreRepository"}]

    result = topological_sorter.get_sorted_node_schema(schemas=schemas.values(), include=["BuiltinLocation"])
    assert result == [{"BuiltinLocation"}]
