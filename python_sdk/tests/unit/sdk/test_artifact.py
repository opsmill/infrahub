import pytest

from infrahub_sdk.exceptions import FeatureNotSupported
from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync

client_types = ["standard", "sync"]


@pytest.mark.parametrize("client_type", client_types)
async def test_node_artifact_generate_raise_featurenotsupported(client, client_type, location_schema, location_data01):
    # node does not inherit from CoreArtifactTarget
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)
        with pytest.raises(FeatureNotSupported):
            await node.artifact_generate("artifact_definition")
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)
        with pytest.raises(FeatureNotSupported):
            node.artifact_generate("artifact_definition")


@pytest.mark.parametrize("client_type", client_types)
async def test_node_artifact_fetch_raise_featurenotsupported(client, client_type, location_schema, location_data01):
    # node does not inherit from CoreArtifactTarget
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)
        with pytest.raises(FeatureNotSupported):
            await node.artifact_fetch("artifact_definition")
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)
        with pytest.raises(FeatureNotSupported):
            node.artifact_fetch("artifact_definition")


@pytest.mark.parametrize("client_type", client_types)
async def test_node_generate_raise_featurenotsupported(client, client_type, location_schema, location_data01):
    # node not of kind CoreArtifactDefinition
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)
        with pytest.raises(FeatureNotSupported):
            await node.generate("artifact_definition")
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)
        with pytest.raises(FeatureNotSupported):
            node.generate("artifact_definition")


@pytest.mark.parametrize("client_type", client_types)
async def test_node_artifact_definition_generate(
    clients,
    client_type,
    mock_rest_api_artifact_definition_generate,
    artifact_definition_schema,
    artifact_definition_data,
):
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=artifact_definition_schema, data=artifact_definition_data)
        await node.generate()
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=artifact_definition_schema, data=artifact_definition_data)
        node.generate()


@pytest.mark.parametrize("client_type", client_types)
async def test_node_artifact_fetch(clients, client_type, mock_rest_api_artifact_fetch, device_schema, device_data):
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=device_schema, data=device_data)
        artifact_content = await node.artifact_fetch("startup-config")
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=device_schema, data=device_data)
        artifact_content = node.artifact_fetch("startup-config")

    assert (
        artifact_content
        == """!device startup config
ip name-server 1.1.1.1
"""
    )


@pytest.mark.parametrize("client_type", client_types)
async def test_node_artifact_generate(
    clients, client_type, mock_rest_api_artifact_generate, device_schema, device_data
):
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=device_schema, data=device_data)
        await node.artifact_generate("startup-config")
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=device_schema, data=device_data)
        node.artifact_generate("startup-config")
