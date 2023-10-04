import pytest

import ipaddress
from unittest.mock import patch

from infrahub_client import InfrahubClient, InfrahubClientSync
from infrahub_client.schema import NodeSchema

from nornir_infrahub.plugins.inventory.infrahub import InfrahubInventory


@pytest.fixture
async def client() -> InfrahubClient:
    return await InfrahubClient.init(address="http://mock", insert_tracker=True, pagination_size=3)


@pytest.fixture
async def client_sync() -> InfrahubClientSync:
    return InfrahubClientSync.init(address="http://mock", insert_tracker=True, pagination_size=3),


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
async def mock_infrahub_inventory(mock_client) -> InfrahubInventory:
    return InfrahubInventory(
        host_node={"kind": "Host", "include": ["attributes.name"]},
        address="http://mock",
        token="your_api_token",
        branch="test-branch",
        schema_mappings=[{"name": "mapping1", "mapping": "attributes.name"}],
        group_mappings=["group1", "group2"],
        defaults_file="defaults.yaml",
        group_file="groups.yaml",
    )
