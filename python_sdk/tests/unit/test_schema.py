import inspect

import pytest

from infrahub_client import InfrahubClient, InfrahubClientSync
from infrahub_client.schema import InfrahubSchema, InfrahubSchemaSync, NodeSchema

async_schema_methods = [method for method in dir(InfrahubSchema) if not method.startswith("_")]
sync_schema_methods = [method for method in dir(InfrahubSchemaSync) if not method.startswith("_")]

client_types = ["standard", "sync"]


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_schema_methods
    assert async_schema_methods == sync_schema_methods


@pytest.mark.parametrize("method", async_schema_methods)
async def test_validate_method_signature(method):
    async_method = getattr(InfrahubSchema, method)
    sync_method = getattr(InfrahubSchemaSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)
    assert async_sig.parameters == sync_sig.parameters
    assert async_sig.return_annotation == sync_sig.return_annotation


@pytest.mark.parametrize("client_type", client_types)
async def test_fetch_schema(mock_schema_query_01, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        client = await InfrahubClient.init(address="http://mock", insert_tracker=True)
        nodes = await client.schema.fetch(branch="main")
    else:
        client = InfrahubClientSync.init(address="http://mock", insert_tracker=True)
        nodes = client.schema.fetch(branch="main")

    assert len(nodes) == 3
    assert sorted(nodes.keys()) == ["GraphQLQuery", "Repository", "Tag"]
    assert isinstance(nodes["Tag"], NodeSchema)
