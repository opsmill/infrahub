import pytest
from pytest_httpx import HTTPXMock

from infrahub_sdk.exceptions import GraphQLError

client_types = ["standard", "sync"]

@pytest.mark.parametrize("client_type", client_types)
async def test_batch_return_exception(httpx_mock: HTTPXMock, mock_query_mutation_location_create_failed, clients, location_schema, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        batch = await clients.standard.create_batch(return_exceptions=True)
        locations = ["JFK1", "JFK1"]
        results = []
        for location_name in locations:
            data = {
                "name": {"value": location_name, "is_protected": True}
            }
            obj = await clients.standard.create(kind="BuiltinLocation", data=data)
            batch.add(task=obj.save, node=obj)
            results.append(obj)

        result_iter = batch.execute()
        # Assert first node success
        node, result = await anext(result_iter)
        assert node == results[0]
        assert not isinstance(result, Exception)

        # Assert second node failure
        node, result = await anext(result_iter)
        assert node == results[1]
        assert isinstance(result, GraphQLError)
        assert "An error occured while executing the GraphQL Query" in str(result)

    else:
        with pytest.raises(NotImplementedError):
            batch = clients.sync.create_batch()

@pytest.mark.parametrize("client_type", client_types)
async def test_batch_exception(httpx_mock: HTTPXMock, mock_query_mutation_location_create_failed, clients, location_schema, client_type):  # pylint: disable=unused-argument

    if client_type == "standard":
        batch = await clients.standard.create_batch(return_exceptions=False)
        locations = ["JFK1", "JFK1"]
        for location_name in locations:
            data = {
                "name": {"value": location_name, "is_protected": True}
            }
            obj = await clients.standard.create(kind="BuiltinLocation", data=data)
            batch.add(task=obj.save, node=obj)

        with pytest.raises(GraphQLError) as exc:
            async for node, result in batch.execute():
                pass
        assert "An error occurred while executing the GraphQL Query" in str(exc.value)

    else:
        with pytest.raises(NotImplementedError):
            batch = clients.sync.create_batch()
