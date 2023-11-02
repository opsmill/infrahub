import ipaddress
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient, InfrahubNodeSync, NodeSchema
from nornir.core.inventory import ConnectionOptions, Defaults  # , HostOrGroup
from nornir_infrahub.plugins.inventory.infrahub import (  # _get_inventory_element,
    HostNode,
    SchemaMappingNode,
    _get_connection_options,
    _get_defaults,
    get_related_nodes,
    ip_interface_to_ip_string,
    resolve_node_mapping,
)
from pydantic.error_wrappers import ValidationError

# from unittest.mock import Mock, patch


# ip_interface_to_ip_string


def test_ip_interface_to_ip_string_ipv4():
    ip_interface = ipaddress.IPv4Interface("192.168.1.1/24")
    result = ip_interface_to_ip_string(ip_interface)
    assert result == "192.168.1.1"


def test_ip_interface_to_ip_string_ipv6():
    ip_interface = ipaddress.IPv6Interface("2001:db8::1/64")
    result = ip_interface_to_ip_string(ip_interface)
    assert result == "2001:db8::1"


# resolve_node_mapping


def test_valid_mapping(client: InfrahubClient, ipaddress_schema: NodeSchema, ipaddress_data: dict[str, Any]):
    node = InfrahubNodeSync(client=client, schema=ipaddress_schema, data=ipaddress_data)
    attrs = ["address"]
    result = resolve_node_mapping(node, attrs)
    assert result == "192.168.1.1"


def test_unsupported_cardinality(client: InfrahubClient, location_schema: NodeSchema):
    node = InfrahubNodeSync(client=client, schema=location_schema)
    attrs = ["tags"]
    with pytest.raises(RuntimeError, match="Relations with many cardinality are not supported!"):
        resolve_node_mapping(node, attrs)


def test_invalid_mapping(client: InfrahubClient, ipaddress_schema: NodeSchema):
    node = InfrahubNodeSync(client=client, schema=ipaddress_schema)
    attrs = ["invalid_attribute"]
    with pytest.raises(RuntimeError, match="Unable to resolve mapping"):
        resolve_node_mapping(node, attrs)


# _get_connection_options


def test_get_connection_options():
    data = {
        "connection1": {
            "hostname": "example.com",
            "port": 22,
            "username": "user1",
            "password": "password1",
            "platform": "cisco",
            "extras": {"key1": "value1"},
        },
        "connection2": {
            "hostname": "test.com",
            "port": 2222,
            "username": "user2",
            "password": "password2",
            "platform": "juniper",
            "extras": {"key2": "value2"},
        },
    }

    result = _get_connection_options(data)

    # expected_result = {
    #     "connection1": ConnectionOptions(
    #         hostname="example.com",
    #         port=22,
    #         username="user1",
    #         password="password1",
    #         platform="linux",
    #         extras={"key1": "value1"},
    #     ),
    #     "connection2": ConnectionOptions(
    #         hostname="test.com",
    #         port=2222,
    #         username="user2",
    #         password="password2",
    #         platform="windows",
    #         extras={"key2": "value2"},
    #     ),
    # }

    # assert resul == expected_result
    assert isinstance(result["connection1"], ConnectionOptions)
    assert isinstance(result["connection2"], ConnectionOptions)


# _get_defaults


def test_get_defaults():
    data = {
        "hostname": "example.com",
        "port": 22,
        "username": "user1",
        "password": "password1",
        "platform": "linux",
        "data": {"key": "value"},
        "connection_options": {
            "connection1": {
                "hostname": "example.com",
                "port": 22,
                "username": "user1",
                "password": "password1",
                "platform": "linux",
                "extras": {"key1": "value1"},
            }
        },
    }

    result = _get_defaults(data)

    # expected_result = Defaults(
    #     hostname="example.com",
    #     port=22,
    #     username="user1",
    #     password="password1",
    #     platform="linux",
    #     data={"key": "value"},
    #     connection_options={
    #         "connection1": ConnectionOptions(
    #             hostname="example.com",
    #             port=22,
    #             username="user1",
    #             password="password1",
    #             platform="linux",
    #             extras={"key1": "value1"},
    #         )
    #     },
    # )

    # assert result == expected_result
    assert isinstance(result, Defaults)


# _get_inventory_element


# XXX fails atm - TypeError: 'TypeVar' object is not callable
# def test_get_inventory_element():
#     data = {
#         "hostname": "example.com",
#         "port": 22,
#         "username": "user1",
#         "password": "password1",
#         "platform": "cisco",
#         "data": {"key": "value"},
#         "groups": ["group1", "group2"],
#         "connection_options": {
#             "connection1": {
#                 "hostname": "example.com",
#                 "port": 22,
#                 "username": "user1",
#                 "password": "password1",
#                 "platform": "cisco",
#                 "extras": {"key1": "value1"},
#             }
#         },
#     }
#     name = "test_host"
#     defaults = Defaults(
#         hostname="default.com",
#         port=2222,
#         username="default_user",
#         password="default_password",
#         platform="default_platform",
#         data={"default_key": "default_value"},
#         connection_options={},
#     )

#     result = _get_inventory_element(HostOrGroup, data, name, defaults)

#     # expected_result = HostOrGroup(
#     #     name="test_host",
#     #     hostname="example.com",
#     #     port=22,
#     #     username="user1",
#     #     password="password1",
#     #     platform="linux",
#     #     data={"key": "value"},
#     #     groups=["group1", "group2"],
#     #     defaults=defaults,
#     #     connection_options={
#     #         "connection1": ConnectionOptions(
#     #             hostname="example.com",
#     #             port=22,
#     #             username="user1",
#     #             password="password1",
#     #             platform="linux",
#     #             extras={"key1": "value1"},
#     #         )
#     #     },
#     # )

#     # assert result == expected_result
#     assert isinstance(result, HostOrGroup)


# SchemaMappingNode


def test_create_schema_mapping_node():
    name = "node_name"
    mapping = "node_mapping"
    node = SchemaMappingNode(name, mapping)

    assert node.name == name
    assert node.mapping == mapping


def test_schema_mapping_node_equality():
    node1 = SchemaMappingNode("node1", "mapping1")
    node2 = SchemaMappingNode("node1", "mapping1")
    node3 = SchemaMappingNode("node2", "mapping2")

    assert node1 == node2
    assert node1 != node3


# HostNode


def test_create_host_node():
    kind = "host"
    include = ["item1", "item2"]
    exclude = ["item3", "item4"]
    filters = {"key1": "value1", "key2": "value2"}

    host_node = HostNode(kind=kind, include=include, exclude=exclude, filters=filters)

    assert host_node.kind == kind
    assert host_node.include == ["member_of_groups", "item1", "item2"]
    assert host_node.exclude == exclude
    assert host_node.filters == filters


def test_validate_include_property():
    valid_include = ["item1", "item2"]
    valid_host_node = HostNode(kind="host", include=valid_include)

    assert valid_host_node.include == ["member_of_groups", "item1", "item2"]

    invalid_include = 123
    with pytest.raises(ValidationError, match="value is not a valid list"):
        HostNode(kind="host", include=invalid_include)

    invalid_include_items = ["item1", [123]]
    with pytest.raises(ValidationError, match="str type expected"):
        HostNode(kind="host", include=invalid_include_items)


# get_related_nodes


def test_get_related_nodes():
    schema = {
        "name": "Person",
        "namespace": "Test",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "vehicules", "peer": "TestVehicule", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }
    node_schema = NodeSchema(**schema)
    attrs = {"vehicules", "address"}  # "Address" is not in the relationships
    result = get_related_nodes(node_schema, attrs)
    expected_result = {"CoreStandardGroup", "TestVehicule"}
    assert result == expected_result


# InfrahubInventory


# XXX fails atm
# def test_infrahub_inventory_load(mock_infrahub_inventory):
#     mock_defaults_content = """
#     """
#     mock_group_content = """
#     """

#     with patch(
#         "builtins.open", side_effect=[Mock(read_data=mock_defaults_content), Mock(read_data=mock_group_content)]
#     ):
#         inventory = mock_infrahub_inventory.load()

#     print(inventory.hosts.keys())
#     print(inventory.groups.keys())

#     assert len(inventory.hosts) > 0
#     assert len(inventory.groups) > 0
#     assert isinstance(inventory.defaults, HostNode)  # Check if defaults were loaded correctly
#     assert inventory.defaults.hostname == "default-host"  # Check values in the defaults
#     assert "Group" in inventory.extra_nodes  # Check if the extra nodes were retrieved


# XXX todo
# def test_infrahub_inventory_get_resources():
#     pass
