import ipaddress
from unittest.mock import patch

import pytest
from infrahub_sdk import InfrahubClient, InfrahubClientSync
from infrahub_sdk.schema import NodeSchema
from nornir_infrahub.plugins.inventory.infrahub import InfrahubInventory


@pytest.fixture
async def client() -> InfrahubClient:
    return await InfrahubClient.init(address="http://mock", insert_tracker=True, pagination_size=3)


@pytest.fixture
async def client_sync() -> InfrahubClientSync:
    return (InfrahubClientSync.init(address="http://mock", insert_tracker=True, pagination_size=3),)


@pytest.fixture
async def location_schema() -> NodeSchema:
    data = {
        "name": "Location",
        "namespace": "Builtin",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "type", "kind": "String"},
        ],
        "relationships": [
            {"name": "tags", "peer": "BuiltinTag", "optional": True, "cardinality": "many"},
            {"name": "primary_tag", "peer": "BuiltinTag", "optional": True, "cardinality": "one"},
            {"name": "member_of_groups", "peer": "CoreGroup", "optional": True, "cardinality": "many", "kind": "Group"},
        ],
    }
    return NodeSchema(**data)


@pytest.fixture
async def device_schema() -> NodeSchema:
    data = {
        "name": "Device",
        "namespace": "Infra",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "type", "kind": "String"},
        ],
        "relationships": [
            {"name": "site", "peer": "BuiltinLocation", "cardinality": "one"},
            {"name": "status", "peer": "BuiltinStatus", "cardinality": "one"},
            {"name": "role", "peer": "BuiltinRole", "cardinality": "one"},
            {"name": "interfaces", "peer": "InfraInterface", "optional": True},
            {"name": "asn", "peer": "InfraAutonomousSystem", "optional": True, "cardinality": "one"},
            {"name": "tag", "peer": "BuiltinTag", "optional": True},
            {"name": "primary_address", "peer": "InfraIPAddress", "optional": True, "cardinality": "one"},
            {"name": "platform", "peer": "InfraPlatform", "optional": True, "cardinality": "one"},
            {"name": "artifacts", "peer": "CoreArtifact", "optional": True},
            {"name": "member_of_groups", "peer": "CoreGroup", "optional": True, "cardinality": "many", "kind": "Group"},
            {
                "name": "subscriber_of_groups",
                "peer": "CoreGroup",
                "optional": True,
                "cardinality": "many",
                "kind": "Group",
            },
        ],
    }
    return NodeSchema(**data)


@pytest.fixture
async def ipaddress_schema() -> NodeSchema:
    data = {
        "name": "IPAddress",
        "namespace": "Infra",
        "default_filter": "address__value",
        "display_labels": ["address_value"],
        "order_by": ["address_value"],
        "attributes": [
            {"name": "address", "kind": "IPHost"},
        ],
        "relationships": [
            {"name": "interface", "peer": "InfraInterfaceL3", "optional": True, "cardinality": "one", "kind": "Parent"}
        ],
    }
    return NodeSchema(**data)


@pytest.fixture
async def ipaddress_data():
    data = {
        "id": "aaaaaaaaaaaaaa",
        "address": {
            "value": ipaddress.ip_interface("192.168.1.1/24"),
            "is_protected": True,
        },
    }
    return data


@pytest.fixture
@patch("nornir_infrahub.plugins.inventory.infrahub.InfrahubClientSync")
@patch("nornir_infrahub.plugins.inventory.infrahub.get_related_nodes")
async def mock_infrahub_inventory(mock_get_related_nodes, mock_infrahub_client) -> InfrahubInventory:
    mock_infrahub_client.schema.get.return_value = device_schema
    mock_get_related_nodes.return_value = {
        "CoreStandardGroup",
    }

    inventory = InfrahubInventory(
        host_node={"kind": "InfraDevice", "include": ["hostname", "platform"]},  # Adjust the parameters as needed
        address="http://example.com",
        token="your_api_token",
        branch="test-branch",
        schema_mappings=[
            {"name": "hostname", "mapping": "primary_address.address"},
            {"name": "platform", "mapping": "platform.nornir_platform"},
        ],
        group_mappings=["site.name"],
        defaults_file="defaults.yaml",
        group_file="groups.yaml",
    )

    return inventory
